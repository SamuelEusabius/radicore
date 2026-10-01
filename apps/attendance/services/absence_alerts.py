"""
Absence alert engine.

Detects students absent for 3+ consecutive SCHOOL days (weekends skipped)
and creates Alert records for their school admins.

Idempotent: uses Alert.rule_code + related_object_id to avoid duplicates.
Auto-resolves: when a student returns, existing alerts are marked resolved.
"""
from datetime import date, timedelta
from django.utils import timezone

RULE_CODE = 'consecutive_absence_3'
ALERT_TITLE_TEMPLATE = "{name} — 3+ consecutive absent days"
ALERT_DESCRIPTION_TEMPLATE = (
    "{name} ({adm}) in {cls} has been absent for {streak} consecutive school days "
    "({start} to {end}). Please follow up with the guardian."
)


def _is_school_day(d):
    """Saturday (5) and Sunday (6) are not school days."""
    return d.weekday() < 5


def _previous_school_day(d):
    """Return the previous school day before d."""
    d = d - timedelta(days=1)
    while not _is_school_day(d):
        d -= timedelta(days=1)
    return d


def count_consecutive_absent_days(student, as_of_date=None):
    """
    Returns (streak, start_date, end_date) if student is currently on an
    absence streak ending on as_of_date. Else returns (0, None, None).

    Walks backwards from as_of_date through school days. Stops at first
    day that is Present / Late / Excused / not recorded (assume returned).
    """
    from apps.attendance.models import Attendance

    if as_of_date is None:
        as_of_date = date.today()

    # If today is weekend, roll back to last school day
    while not _is_school_day(as_of_date):
        as_of_date -= timedelta(days=1)

    streak = 0
    end_date = None
    start_date = None
    d = as_of_date

    while True:
        if not _is_school_day(d):
            d = _previous_school_day(d)
            continue

        record = Attendance.objects.filter(student=student, date=d).first()

        if record is None or record.status != 'A':
            # No record or not absent → streak broke
            break

        streak += 1
        end_date = end_date or d
        start_date = d

        d = _previous_school_day(d)

        # Safety: don't scan forever
        if streak > 30:
            break

    if streak == 0:
        return 0, None, None
    return streak, start_date, end_date


def run_absence_check(school=None, threshold=3, as_of_date=None):
    """
    Scans all active students (or one school) and:
      - Creates new alerts for students on a streak >= threshold
      - Auto-resolves alerts for students whose streak broke

    Returns dict summary: {'scanned': N, 'new_alerts': N, 'resolved': N}
    """
    from apps.students.models import Student
    from apps.notifications.models import Alert

    if as_of_date is None:
        as_of_date = date.today()

    students_qs = Student.objects.filter(is_active=True).select_related('school')
    if school is not None:
        students_qs = students_qs.filter(school=school)

    summary = {'scanned': 0, 'new_alerts': 0, 'resolved': 0, 'still_absent': 0}

    for student in students_qs:
        summary['scanned'] += 1

        streak, start_date, end_date = count_consecutive_absent_days(student, as_of_date)

        # Existing open alert for this student+rule?
        existing_open = Alert.objects.filter(
            rule_code=RULE_CODE,
            related_object_type='Student',
            related_object_id=student.id,
            status__in=[Alert.Status.NEW, Alert.Status.REVIEWING],
        ).first()

        if streak >= threshold:
            summary['still_absent'] += 1

            if not existing_open:
                # Get admins for this school
                admins = student.school.users.filter(role__in=['school_admin', 'super_admin']) \
                    if hasattr(student.school, 'users') else []

                # Create the alert (school-scoped, not per-user)
                Alert.objects.create(
                    school=student.school,
                    severity=Alert.Severity.HIGH,
                    status=Alert.Status.NEW,
                    category=Alert.Category.ACADEMIC,
                    title=ALERT_TITLE_TEMPLATE.format(name=student.full_name),
                    description=ALERT_DESCRIPTION_TEMPLATE.format(
                        name=student.full_name,
                        adm=student.admission_number,
                        cls=student.class_level or '—',
                        streak=streak,
                        start=start_date.strftime('%d %b'),
                        end=end_date.strftime('%d %b %Y'),
                    ),
                    rule_code=RULE_CODE,
                    related_object_type='Student',
                    related_object_id=student.id,
                    metadata={
                        'streak': streak,
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'admission_number': student.admission_number,
                        'class_level': student.class_level or '',
                        'guardian_phone': student.guardian_phone or '',
                    },
                )
                summary['new_alerts'] += 1

        else:
            # Streak broke — auto-resolve any open alert
            if existing_open:
                existing_open.resolve(
                    user=None,
                    notes=f'Auto-resolved: student resumed on {as_of_date.isoformat()}',
                )
                summary['resolved'] += 1

    return summary