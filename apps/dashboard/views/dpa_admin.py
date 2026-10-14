"""
Deputy Principal — Administration dashboard views.

Covers discipline, staff leave, duty rosters, and staff attendance.
"""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q

from apps.accounts.roles import Role
from apps.discipline.models import (
    DisciplineRecord, DisciplineAction,
    DisciplineCategory, DisciplineSeverity, DisciplineStatus,
    StudentLeaveOut, LeaveOutType, LeaveOutStatus, SuspensionReason,
)
from apps.staff.models import (
    LeaveRequest, DutyRoster, StaffAttendance, StaffMovement,
    LeaveType, LeaveStatus,
    DutyType, StaffAttendanceStatus, MovementDirection,
)
from apps.students.models import (
    Student, StudentMovement, StudentAdminCase,
    StudentMovementDirection, StudentMovementReason,
    AdminCaseType, AdminCaseStatus, AdminCasePriority,
)

from apps.core.pdf_utils import build_pdf_context
from apps.attendance.models import Attendance

def _require_dpa(request):
    """Return True if current user may see the DPA dashboard."""
    if not request.user.is_authenticated:
        return False
    return request.user.role in (Role.DEPUTY_ADMIN, Role.PRINCIPAL)


@login_required
def dpa_admin_dashboard(request):
    """Deputy Principal — Administration landing page."""
    if not _require_dpa(request):
        return redirect('dashboard_home')

    school = getattr(request.user, 'school', None)
    if school is None:
        messages.error(request, 'Your account is not linked to a school.')
        return redirect('dashboard_home')

    today = timezone.localdate()

    # ---------------- Discipline KPIs ----------------
    open_cases = DisciplineRecord.objects.filter(
        school=school,
        status__in=[
            DisciplineStatus.OPEN,
            DisciplineStatus.INVESTIGATING,
            DisciplineStatus.ESCALATED,
        ],
    )
    discipline_stats = {
        'total_open':  open_cases.count(),
        'critical':    open_cases.filter(severity=DisciplineSeverity.CRITICAL).count(),
        'serious':     open_cases.filter(severity=DisciplineSeverity.SERIOUS).count(),
        'moderate':    open_cases.filter(severity=DisciplineSeverity.MODERATE).count(),
        'minor':       open_cases.filter(severity=DisciplineSeverity.MINOR).count(),
    }

    recent_discipline = open_cases.select_related('student').order_by(
        '-incident_date', '-created_at'
    )[:5]

    # ---------------- Leave KPIs ----------------
    pending_leave = LeaveRequest.objects.filter(
        school=school, status=LeaveStatus.PENDING
    ).select_related('staff')

    leave_stats = {
        'pending_dpa':       pending_leave.filter(dpa_approved_at__isnull=True).count(),
        'pending_principal': pending_leave.filter(
            dpa_approved_at__isnull=False,
            principal_approved_at__isnull=True,
        ).count(),
        'approved_this_month': LeaveRequest.objects.filter(
            school=school,
            status=LeaveStatus.APPROVED,
            start_date__gte=today.replace(day=1),
        ).count(),
    }

    leave_queue = pending_leave.filter(dpa_approved_at__isnull=True).order_by('start_date')[:5]

    # ---------------- Duty roster ----------------
    todays_duties = DutyRoster.objects.filter(
        school=school, duty_date=today
    ).select_related('staff').order_by('start_time')

    week_end = today + timedelta(days=7)
    upcoming_duties = DutyRoster.objects.filter(
        school=school,
        duty_date__gt=today,
        duty_date__lte=week_end,
    ).count()

    duty_stats = {
        'today_total':     todays_duties.count(),
        'today_done':      todays_duties.filter(completed=True).count(),
        'upcoming_week':   upcoming_duties,
    }

    # ---------------- Staff attendance ----------------
    att_today = StaffAttendance.objects.filter(school=school, date=today)
    attendance_stats = {
        'present':  att_today.filter(status=StaffAttendanceStatus.PRESENT).count(),
        'absent':   att_today.filter(status=StaffAttendanceStatus.ABSENT).count(),
        'late':     att_today.filter(status=StaffAttendanceStatus.LATE).count(),
        'on_leave': att_today.filter(status=StaffAttendanceStatus.ON_LEAVE).count(),
        'recorded': att_today.count(),
    }

    context = {
        'school': school,
        'today': today,
        'discipline_stats': discipline_stats,
        'recent_discipline': recent_discipline,
        'leave_stats': leave_stats,
        'leave_queue': leave_queue,
        'duty_stats': duty_stats,
        'todays_duties': todays_duties,
        'attendance_stats': attendance_stats,
        'can_approve': request.user.role == Role.DEPUTY_ADMIN,
    }
    return render(request, 'dashboards/dpa_admin.html', context)


@login_required
def dpa_approve_leave(request, leave_id):
    """DPA approves a pending leave request → forwards to Principal."""
    if request.user.role != Role.DEPUTY_ADMIN:
        return redirect('dashboard_home')

    leave = get_object_or_404(LeaveRequest, pk=leave_id, school=request.user.school)

    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        leave.dpa_approved_by = request.user
        leave.dpa_approved_at = timezone.now()
        leave.dpa_comment = comment
        leave.save(update_fields=['dpa_approved_by', 'dpa_approved_at', 'dpa_comment', 'updated_at'])
        messages.success(request, f"Leave for {leave.staff.get_full_name() or leave.staff.email} approved. Sent to Principal.")

    return redirect('dpa_admin_dashboard')


@login_required
def dpa_reject_leave(request, leave_id):
    """DPA rejects a leave request."""
    if request.user.role != Role.DEPUTY_ADMIN:
        return redirect('dashboard_home')

    leave = get_object_or_404(LeaveRequest, pk=leave_id, school=request.user.school)

    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        leave.status = LeaveStatus.REJECTED
        leave.dpa_approved_by = request.user
        leave.dpa_approved_at = timezone.now()
        leave.dpa_comment = comment
        leave.save(update_fields=['status', 'dpa_approved_by', 'dpa_approved_at', 'dpa_comment', 'updated_at'])
        messages.warning(request, f"Leave for {leave.staff.get_full_name() or leave.staff.email} rejected.")

    return redirect('dpa_admin_dashboard')


@login_required
def dpa_discipline_list(request):
    """Full discipline case list with filters."""
    if not _require_dpa(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = DisciplineRecord.objects.filter(school=school).select_related('student', 'reported_by')

    # Filters
    status = request.GET.get('status', '').strip()
    severity = request.GET.get('severity', '').strip()
    search = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
            | Q(description__icontains=search)
        )

    qs = qs.order_by('-incident_date', '-created_at')

    context = {
        'school': school,
        'records': qs[:200],
        'total': qs.count(),
        'status_filter': status,
        'severity_filter': severity,
        'search': search,
        'status_choices': DisciplineStatus.choices,
        'severity_choices': DisciplineSeverity.choices,
    }
    return render(request, 'dashboards/dpa_admin_discipline.html', context)
  
  

# ==========================================================
# DISCIPLINE DETAIL + CRUD
# ==========================================================

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden


def dpa_required(view_func):
    """
    Restrict view to DPA Admin, Principal, or Super Admin.
    Ensures the user has a school set.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if request.user.role not in (Role.DEPUTY_ADMIN, Role.PRINCIPAL, Role.SUPER_ADMIN):
            return HttpResponseForbidden("You do not have access to this page.")
        if request.user.school is None:
            return HttpResponseForbidden("Your account is not linked to a school.")
        return view_func(request, *args, **kwargs)
    return wrapper


@dpa_required
def dpa_discipline_detail(request, record_id):
    """Full detail view for one discipline record."""
    record = get_object_or_404(
        DisciplineRecord.objects.select_related('student', 'reported_by', 'handled_by'),
        pk=record_id, school=request.user.school,
    )

    actions = record.actions.select_related('performed_by').all()
    leave_outs = record.leave_outs.select_related(
        'requested_by', 'dpa_approved_by', 'principal_approved_by'
    ).all()
    committee_decisions = record.committee_decisions.select_related(
        'meeting', 'meeting__committee', 'recorded_by'
    ).all()

    context = {
        'school': request.user.school,
        'record': record,
        'actions': actions,
        'leave_outs': leave_outs,
        'committee_decisions': committee_decisions,
        'can_edit': request.user.role in (Role.DEPUTY_ADMIN, Role.PRINCIPAL),
        'leave_out_types': LeaveOutType.choices,
        'suspension_reasons': SuspensionReason.choices,
        'severity_choices': DisciplineSeverity.choices,
        'status_choices': DisciplineStatus.choices,
    }
    return render(request, 'dashboards/dpa/discipline_detail.html', context)


@dpa_required
def dpa_discipline_create(request):
    """Record a new discipline case."""
    from apps.students.models import Student
    import json

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        category = request.POST.get('category')
        severity = request.POST.get('severity', 'minor')
        description = request.POST.get('description', '').strip()
        incident_date = request.POST.get('incident_date')
        incident_time = request.POST.get('incident_time') or None
        location = request.POST.get('location', '').strip()

        if not student_id or not category or not description or not incident_date:
            messages.error(request, 'Please select a student and fill in category, description, and date.')
        else:
            try:
                student = Student.objects.for_user(request.user).get(pk=student_id)
                record = DisciplineRecord.objects.create(
                    school=request.user.school,
                    student=student,
                    category=category,
                    severity=severity,
                    description=description,
                    incident_date=incident_date,
                    incident_time=incident_time,
                    location=location,
                    reported_by=request.user,
                )
                messages.success(request, f"Discipline case recorded for {student.first_name}.")
                return redirect('dpa_discipline_detail', record_id=record.id)
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    # Preload student list for searchable picker
    students_qs = Student.objects.for_user(request.user).filter(
        is_active=True
    ).order_by('class_level', 'first_name', 'last_name').only(
        'id', 'first_name', 'last_name', 'admission_number', 'class_level'
    )

    students_json = json.dumps([
        {
            'id': s.id,
            'name': f"{s.first_name} {s.last_name}".strip(),
            'adm': s.admission_number or '',
            'cls': s.class_level or '',
        }
        for s in students_qs
    ])

    context = {
        'school': request.user.school,
        'students_json': students_json,
        'categories': DisciplineCategory.choices,
        'severities': DisciplineSeverity.choices,
        'today': timezone.localdate(),
    }
    return render(request, 'dashboards/dpa/discipline_form.html', context)

@dpa_required
def dpa_discipline_edit(request, record_id):
    """Edit an existing discipline case."""
    record = get_object_or_404(
        DisciplineRecord, pk=record_id, school=request.user.school,
    )

    if request.method == 'POST':
        record.category = request.POST.get('category', record.category)
        record.severity = request.POST.get('severity', record.severity)
        record.description = request.POST.get('description', record.description)
        record.incident_date = request.POST.get('incident_date', record.incident_date)
        record.incident_time = request.POST.get('incident_time') or record.incident_time
        record.location = request.POST.get('location', record.location)
        record.status = request.POST.get('status', record.status)
        record.resolution_notes = request.POST.get('resolution_notes', record.resolution_notes)
        record.save()
        messages.success(request, 'Case updated.')
        return redirect('dpa_discipline_detail', record_id=record.id)

    context = {
        'school': request.user.school,
        'record': record,
        'categories': DisciplineCategory.choices,
        'severities': DisciplineSeverity.choices,
        'statuses': DisciplineStatus.choices,
    }
    return render(request, 'dashboards/dpa/discipline_form.html', context)


@dpa_required
def dpa_discipline_escalate(request, record_id):
    """Change status to escalated. POST only."""
    if request.method != 'POST':
        return redirect('dpa_discipline_detail', record_id=record_id)

    record = get_object_or_404(
        DisciplineRecord, pk=record_id, school=request.user.school,
    )
    record.status = DisciplineStatus.ESCALATED
    record.handled_by = request.user
    record.handled_at = timezone.now()
    comment = request.POST.get('comment', '').strip()
    if comment:
        record.resolution_notes = (record.resolution_notes + '\n\n' + comment).strip()
    record.save()
    messages.success(request, 'Case escalated to the Principal.')
    return redirect('dpa_discipline_detail', record_id=record.id)


@dpa_required
def dpa_leave_out_create(request, record_id):
    """Create a leave-out (suspension/expulsion) from a discipline case."""
    record = get_object_or_404(
        DisciplineRecord, pk=record_id, school=request.user.school,
    )

    if request.method == 'POST':
        leave_out_type = request.POST.get('leave_out_type', LeaveOutType.SUSPENSION)
        suspension_reason = request.POST.get('suspension_reason', '')
        reason_description = request.POST.get('reason_description', '').strip()
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None

        if not reason_description or not start_date:
            messages.error(request, 'Reason and start date are required.')
        else:
            leave = StudentLeaveOut.objects.create(
                school=request.user.school,
                student=record.student,
                leave_out_type=leave_out_type,
                suspension_reason=suspension_reason,
                reason_description=reason_description,
                discipline_record=record,
                start_date=start_date,
                end_date=end_date,
                requested_by=request.user,
                status=LeaveOutStatus.PENDING,
            )
            messages.success(request, f"Leave-out recorded for {record.student.first_name}. Now pending approval.")
            return redirect('dpa_discipline_detail', record_id=record.id)

    context = {
        'school': request.user.school,
        'record': record,
        'leave_out_types': LeaveOutType.choices,
        'suspension_reasons': SuspensionReason.choices,
        'today': timezone.localdate(),
    }
    return render(request, 'dashboards/dpa/leave_out_form.html', context)


@dpa_required
def dpa_leave_out_approve(request, leave_out_id):
    """DPA approves a leave-out → moves to principal for expulsion cases."""
    if request.method != 'POST':
        return redirect('dpa_admin_dashboard')

    leave = get_object_or_404(
        StudentLeaveOut, pk=leave_out_id, school=request.user.school,
    )
    leave.dpa_approved_by = request.user
    leave.dpa_approved_at = timezone.now()
    leave.dpa_comment = request.POST.get('comment', '').strip()

    if leave.leave_out_type == LeaveOutType.EXPULSION:
        # Expulsion requires Principal — leave status PENDING until principal approves
        leave.save(update_fields=['dpa_approved_by', 'dpa_approved_at', 'dpa_comment', 'updated_at'])
        messages.info(request, 'Expulsion forwarded to Principal for final approval.')
    else:
        leave.status = LeaveOutStatus.APPROVED
        leave.save(update_fields=['dpa_approved_by', 'dpa_approved_at', 'dpa_comment', 'status', 'updated_at'])
        messages.success(request, 'Leave-out approved.')

    return redirect('dpa_leave_out_detail', leave_out_id=leave.id)


@dpa_required
def dpa_leave_out_detail(request, leave_out_id):
    """Full detail of a leave-out."""
    leave = get_object_or_404(
        StudentLeaveOut.objects.select_related(
            'student', 'discipline_record', 'requested_by',
            'dpa_approved_by', 'principal_approved_by',
        ),
        pk=leave_out_id, school=request.user.school,
    )

    context = {
        'school': request.user.school,
        'leave': leave,
        'can_approve': request.user.role in (Role.DEPUTY_ADMIN, Role.PRINCIPAL),
        'is_expulsion': leave.leave_out_type == LeaveOutType.EXPULSION,
    }
    return render(request, 'dashboards/dpa/leave_out_detail.html', context)


@dpa_required
def dpa_leave_out_toggle_notify(request, leave_out_id):
    """Toggle guardian notified flag."""
    if request.method != 'POST':
        return redirect('dpa_leave_out_detail', leave_out_id=leave_out_id)

    leave = get_object_or_404(
        StudentLeaveOut, pk=leave_out_id, school=request.user.school,
    )
    leave.guardian_notified = True
    leave.guardian_notified_at = timezone.now()
    leave.guardian_notification_method = request.POST.get('method', 'call')
    leave.guardian_acknowledged = request.POST.get('acknowledged') == 'on'
    leave.save()
    messages.success(request, 'Guardian notification recorded.')
    return redirect('dpa_leave_out_detail', leave_out_id=leave.id)


@dpa_required
def dpa_leave_out_list(request):
    """All leave-outs for the school."""
    qs = StudentLeaveOut.objects.filter(
        school=request.user.school
    ).select_related('student').order_by('-start_date')

    status = request.GET.get('status', '').strip()
    lo_type = request.GET.get('type', '').strip()

    if status:
        qs = qs.filter(status=status)
    if lo_type:
        qs = qs.filter(leave_out_type=lo_type)

    context = {
        'school': request.user.school,
        'leave_outs': qs[:200],
        'total': qs.count(),
        'status_filter': status,
        'type_filter': lo_type,
        'status_choices': LeaveOutStatus.choices,
        'type_choices': LeaveOutType.choices,
    }
    return render(request, 'dashboards/dpa/leave_out_list.html', context)
  
  

# ==========================================================
# DISCIPLINE REPORTING — class / grade / school-wide
# ==========================================================

from collections import Counter, defaultdict
from django.db.models import Count, Q
from django.template.loader import render_to_string
from apps.core.pdf_utils import html_to_pdf_response


def _grade_from_class_level(class_level_str):
    """'GRADE 5 WEST' → 'GRADE 5'. 'GRADE 9' → 'GRADE 9'."""
    if not class_level_str:
        return ''
    parts = class_level_str.strip().split()
    if len(parts) >= 2 and parts[0].upper() in ('GRADE', 'FORM'):
        return f"{parts[0].upper()} {parts[1]}"
    return class_level_str.strip()


def _available_class_levels(school):
    """Distinct class_level strings for this school's active students."""
    from apps.students.models import Student
    values = Student.objects.filter(
        school=school, is_active=True,
    ).exclude(class_level='').values_list('class_level', flat=True).distinct().order_by('class_level')
    return list(values)


def _available_grades(school):
    """Derived grade list like ['GRADE 1', 'GRADE 2', ...] sorted sensibly."""
    classes = _available_class_levels(school)
    grades = sorted(set(_grade_from_class_level(c) for c in classes if c))
    # Sort by numeric part
    def sort_key(g):
        parts = g.split()
        if len(parts) == 2 and parts[1].isdigit():
            return (parts[0], int(parts[1]))
        return (g, 0)
    return sorted(grades, key=sort_key)


def _filter_discipline_records(school, scope, grade=None, class_level=None,
                                date_from=None, date_to=None):
    """
    Return a filtered QuerySet of DisciplineRecord for the given scope.

    scope: 'school' | 'grade' | 'class'
    """
    qs = DisciplineRecord.objects.filter(school=school).select_related('student', 'reported_by')

    if scope == 'class' and class_level:
        qs = qs.filter(student__class_level=class_level)
    elif scope == 'grade' and grade:
        qs = qs.filter(student__class_level__startswith=grade)

    if date_from:
        qs = qs.filter(incident_date__gte=date_from)
    if date_to:
        qs = qs.filter(incident_date__lte=date_to)

    return qs.order_by('-incident_date', '-created_at')


def _build_report_data(qs, school):
    """Compute all the aggregates the report templates need."""
    records = list(qs)

    # Category counts
    category_counts = Counter(r.category for r in records)
    category_labels = dict(DisciplineCategory.choices)
    categories = [
        {'label': category_labels.get(k, k), 'count': v}
        for k, v in sorted(category_counts.items(), key=lambda x: -x[1])
    ]

    # Severity counts
    severity_counts = Counter(r.severity for r in records)
    severity_labels = dict(DisciplineSeverity.choices)
    severities = [
        {'label': severity_labels.get(k, k), 'count': severity_counts.get(k, 0)}
        for k in [s[0] for s in DisciplineSeverity.choices]
    ]

    # Status counts
    status_counts = Counter(r.status for r in records)
    status_labels = dict(DisciplineStatus.choices)
    statuses = [
        {'label': status_labels.get(k, k), 'count': v}
        for k, v in status_counts.items()
    ]

    # Per-student aggregation
    students_map = defaultdict(lambda: {
        'student': None,
        'class_level': '',
        'count': 0,
        'categories': Counter(),
        'severities': Counter(),
        'latest_date': None,
    })
    for r in records:
        key = r.student_id
        entry = students_map[key]
        entry['student'] = r.student
        entry['class_level'] = getattr(r.student, 'class_level', '') or ''
        entry['count'] += 1
        entry['categories'][r.category] += 1
        entry['severities'][r.severity] += 1
        if entry['latest_date'] is None or r.incident_date > entry['latest_date']:
            entry['latest_date'] = r.incident_date

    students = sorted(
        students_map.values(),
        key=lambda e: (-e['count'], e['student'].first_name if e['student'] else ''),
    )

    # Per-class aggregation (school or grade scope)
    per_class = defaultdict(lambda: {'class_level': '', 'count': 0, 'students': set()})
    for r in records:
        cl = getattr(r.student, 'class_level', '') or '(no class)'
        per_class[cl]['class_level'] = cl
        per_class[cl]['count'] += 1
        per_class[cl]['students'].add(r.student_id)
    per_class_list = sorted(
        [
            {'class_level': v['class_level'], 'count': v['count'], 'student_count': len(v['students'])}
            for v in per_class.values()
        ],
        key=lambda x: x['class_level'],
    )

    # Top offenders (limit 10)
    top_offenders = [s for s in students if s['count'] >= 2][:10]

    return {
        'records': records,
        'total': len(records),
        'categories': categories,
        'severities': severities,
        'statuses': statuses,
        'students': students,
        'per_class': per_class_list,
        'top_offenders': top_offenders,
    }


@dpa_required
def dpa_discipline_report(request):
    """Discipline report selector page with live preview."""
    school = request.user.school

    scope = request.GET.get('scope', 'school')
    grade = request.GET.get('grade', '').strip()
    class_level = request.GET.get('class', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    # Only compute report if user has actually applied filters
    report = None
    applied = bool(request.GET.get('apply'))

    if applied:
        qs = _filter_discipline_records(
            school, scope, grade, class_level, date_from or None, date_to or None,
        )
        report = _build_report_data(qs, school)

    context = {
        'school': school,
        'scope': scope,
        'grade': grade,
        'class_level': class_level,
        'date_from': date_from,
        'date_to': date_to,
        'available_grades': _available_grades(school),
        'available_classes': _available_class_levels(school),
        'report': report,
        'applied': applied,
        'scope_choices': [
            ('school', 'Entire School'),
            ('grade', 'By Grade (merged streams)'),
            ('class', 'By Single Class'),
        ],
    }
    return render(request, 'dashboards/dpa/discipline_report.html', context)


@dpa_required
def dpa_discipline_report_pdf(request):
    """Generate PDF for the selected scope."""
    school = request.user.school

    scope = request.GET.get('scope', 'school')
    grade = request.GET.get('grade', '').strip()
    class_level = request.GET.get('class', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    qs = _filter_discipline_records(
        school, scope, grade, class_level, date_from or None, date_to or None,
    )
    report = _build_report_data(qs, school)

    # Pick template + scope description
    if scope == 'class' and class_level:
        template = 'pdf/dpa_discipline_class.html'
        scope_desc = f"Class: {class_level}"
        filename_scope = class_level.replace(' ', '_').lower()
    elif scope == 'grade' and grade:
        template = 'pdf/dpa_discipline_grade.html'
        scope_desc = f"Grade: {grade} (Merged Streams)"
        filename_scope = grade.replace(' ', '_').lower()
    else:
        template = 'pdf/dpa_discipline_school.html'
        scope_desc = "Entire School"
        filename_scope = "school"

    period = "All time"
    if date_from and date_to:
        period = f"{date_from} to {date_to}"
    elif date_from:
        period = f"From {date_from}"
    elif date_to:
        period = f"Up to {date_to}"

    html_string = render_to_string(template,
        build_pdf_context(
            school=school,
            generated_by=request.user,
            report=report,
            scope_desc=scope_desc,
            period=period,
            date_from=date_from,
            date_to=date_to,
            grade=grade,
            class_level=class_level,
        )
    )

    filename = f"discipline_{filename_scope}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    return html_to_pdf_response(html_string, filename)

# ==========================================================
# STAFF MANAGEMENT — attendance, duty roster, leave, movement
# ==========================================================

from datetime import timedelta
from django.utils.dateparse import parse_date


def _school_staff(request):
    """All active non-student/non-parent users for this school."""
    from apps.accounts.models import User
    from apps.accounts.roles import Role
    return User.objects.filter(
        school=request.user.school,
        is_active=True,
    ).exclude(
        role__in=[Role.STUDENT, Role.PARENT, Role.SUPER_ADMIN]
    ).order_by('first_name', 'last_name', 'email')


# ==========================================================
# STAFF ATTENDANCE
# ==========================================================

@dpa_required
def dpa_staff_attendance(request):
    """Daily attendance grid — one row per staff member for a chosen date."""
    selected_date_str = request.GET.get('date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else timezone.localdate()

    if request.method == 'POST':
        # Bulk save
        for key, value in request.POST.items():
            if not key.startswith('status_'):
                continue
            staff_id = key.replace('status_', '')
            check_in = request.POST.get(f'check_in_{staff_id}', '').strip() or None
            check_out = request.POST.get(f'check_out_{staff_id}', '').strip() or None

            StaffAttendance.objects.update_or_create(
                school=request.user.school,
                staff_id=staff_id,
                date=selected_date,
                defaults={
                    'status': value,
                    'check_in_time': check_in,
                    'check_out_time': check_out,
                    'recorded_by': request.user,
                },
            )
        messages.success(request, f'Attendance saved for {selected_date}.')
        return redirect(f"{request.path}?date={selected_date.isoformat()}")

    staff_list = _school_staff(request)
    existing = {
        a.staff_id: a
        for a in StaffAttendance.objects.filter(
            school=request.user.school, date=selected_date
        )
    }

    rows = []
    for staff in staff_list:
        att = existing.get(staff.id)
        rows.append({
            'staff': staff,
            'attendance': att,
            'status': att.status if att else 'present',
            'check_in': att.check_in_time if att else None,
            'check_out': att.check_out_time if att else None,
        })

    summary = {
        'present':  sum(1 for r in rows if r['status'] == StaffAttendanceStatus.PRESENT),
        'absent':   sum(1 for r in rows if r['status'] == StaffAttendanceStatus.ABSENT),
        'late':     sum(1 for r in rows if r['status'] == StaffAttendanceStatus.LATE),
        'on_leave': sum(1 for r in rows if r['status'] == StaffAttendanceStatus.ON_LEAVE),
        'total':    len(rows),
    }

    context = {
        'school': request.user.school,
        'selected_date': selected_date,
        'rows': rows,
        'summary': summary,
        'status_choices': StaffAttendanceStatus.choices,
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
    }
    return render(request, 'dashboards/dpa/staff_attendance.html', context)


@dpa_required
def dpa_staff_attendance_history(request):
    """All staff attendance records with filters."""
    qs = StaffAttendance.objects.filter(
        school=request.user.school
    ).select_related('staff', 'recorded_by').order_by('-date', 'staff__first_name')

    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    status = request.GET.get('status', '').strip()

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if status:
        qs = qs.filter(status=status)

    context = {
        'school': request.user.school,
        'records': qs[:500],
        'total': qs.count(),
        'date_from': date_from,
        'date_to': date_to,
        'status_filter': status,
        'status_choices': StaffAttendanceStatus.choices,
    }
    return render(request, 'dashboards/dpa/staff_attendance_history.html', context)


# ==========================================================
# DUTY ROSTER
# ==========================================================

@dpa_required
def dpa_duty_roster(request):
    """Weekly duty roster view."""
    # Anchor date — defaults to today
    anchor_str = request.GET.get('week', '')
    anchor = parse_date(anchor_str) if anchor_str else timezone.localdate()

    # Start of week (Monday)
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=6)

    duties = DutyRoster.objects.filter(
        school=request.user.school,
        duty_date__gte=week_start,
        duty_date__lte=week_end,
    ).select_related('staff', 'assigned_by').order_by('duty_date', 'start_time')

    # Group by date
    by_day = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        by_day[day] = [d for d in duties if d.duty_date == day]

    context = {
        'school': request.user.school,
        'week_start': week_start,
        'week_end': week_end,
        'by_day': by_day,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
        'total_duties': duties.count(),
    }
    return render(request, 'dashboards/dpa/duty_roster.html', context)


@dpa_required
def dpa_duty_create(request):
    """Create duty assignments for multiple staff over a date range."""
    if request.method == 'POST':
        staff_ids = request.POST.getlist('staff_ids')
        duty_type = request.POST.get('duty_type')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        start_time = request.POST.get('start_time') or None
        end_time = request.POST.get('end_time') or None
        location = request.POST.get('location', '').strip()
        notes = request.POST.get('notes', '').strip()
        skip_weekends = request.POST.get('skip_weekends') == 'on'
        skip_holidays = request.POST.get('skip_holidays') == 'on'

        if not staff_ids or not duty_type or not date_from or not date_to:
            messages.error(request, 'Please select at least one staff, duty type, and date range.')
        else:
            try:
                df = parse_date(date_from)
                dt = parse_date(date_to)

                if dt < df:
                    messages.error(request, 'End date must be on or after start date.')
                else:
                    # Build list of dates in range
                    dates = []
                    current = df
                    one_day = timedelta(days=1)
                    while current <= dt:
                        if not (skip_weekends and current.weekday() >= 5):
                            dates.append(current)
                        current += one_day

                    created = 0
                    skipped = 0
                    for staff_id in staff_ids:
                        for d in dates:
                            _, was_created = DutyRoster.objects.get_or_create(
                                school=request.user.school,
                                staff_id=staff_id,
                                duty_date=d,
                                duty_type=duty_type,
                                defaults={
                                    'start_time': start_time,
                                    'end_time': end_time,
                                    'location': location,
                                    'notes': notes,
                                    'assigned_by': request.user,
                                },
                            )
                            if was_created:
                                created += 1
                            else:
                                skipped += 1

                    msg = f'{created} dut{"y" if created == 1 else "ies"} assigned.'
                    if skipped:
                        msg += f' {skipped} already existed and were skipped.'
                    messages.success(request, msg)
                    return redirect(f"/dashboard/dpa-admin/staff/duty-roster/?week={date_from}")
            except Exception as e:
                messages.error(request, f'Error: {e}')

    context = {
        'school': request.user.school,
        'staff_list': _school_staff(request),
        'duty_types': DutyType.choices,
        'today': timezone.localdate(),
    }
    return render(request, 'dashboards/dpa/duty_form.html', context)

@dpa_required
def dpa_duty_toggle_complete(request, duty_id):
    """Mark duty as complete/incomplete."""
    if request.method != 'POST':
        return redirect('dpa_duty_roster')

    duty = get_object_or_404(DutyRoster, pk=duty_id, school=request.user.school)
    duty.completed = not duty.completed
    duty.completed_at = timezone.now() if duty.completed else None
    duty.save(update_fields=['completed', 'completed_at'])
    return redirect(request.META.get('HTTP_REFERER', 'dpa_duty_roster'))


@dpa_required
def dpa_duty_delete(request, duty_id):
    """Delete a duty assignment."""
    if request.method != 'POST':
        return redirect('dpa_duty_roster')

    duty = get_object_or_404(DutyRoster, pk=duty_id, school=request.user.school)
    duty.delete()
    messages.success(request, 'Duty removed.')
    return redirect(request.META.get('HTTP_REFERER', 'dpa_duty_roster'))


# ==========================================================
# LEAVE REQUEST DETAIL + APPROVE/REJECT
# ==========================================================

@dpa_required
def dpa_leave_detail(request, leave_id):
    """Full detail of a leave request with approval actions."""
    leave = get_object_or_404(
        LeaveRequest.objects.select_related(
            'staff', 'dpa_approved_by', 'principal_approved_by'
        ),
        pk=leave_id, school=request.user.school,
    )

    context = {
        'school': request.user.school,
        'leave': leave,
        'can_approve_dpa': (
            request.user.role == Role.DEPUTY_ADMIN
            and leave.dpa_approved_at is None
            and leave.status == LeaveStatus.PENDING
        ),
        'can_approve_principal': (
            request.user.role == Role.PRINCIPAL
            and leave.dpa_approved_at is not None
            and leave.principal_approved_at is None
            and leave.status == LeaveStatus.PENDING
        ),
    }
    return render(request, 'dashboards/dpa/leave_detail.html', context)


@dpa_required
def dpa_leave_list(request):
    """All leave requests."""
    qs = LeaveRequest.objects.filter(
        school=request.user.school
    ).select_related('staff', 'dpa_approved_by', 'principal_approved_by').order_by('-requested_at')

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    # Accurate status counts (from the base queryset, before status filter)
    all_requests = LeaveRequest.objects.filter(school=request.user.school)

    context = {
        'school': request.user.school,
        'leave_requests': qs[:200],
        'total': qs.count(),
        'status_filter': status,
        'status_choices': LeaveStatus.choices,
        # Accurate status breakdown
        'pending_count': all_requests.filter(status=LeaveStatus.PENDING).count(),
        'approved_count': all_requests.filter(status=LeaveStatus.APPROVED).count(),
        'rejected_count': all_requests.filter(status=LeaveStatus.REJECTED).count(),
        'awaiting_dpa_count': all_requests.filter(
            status=LeaveStatus.PENDING,
            dpa_approved_at__isnull=True,
        ).count(),
    }
    return render(request, 'dashboards/dpa/leave_list.html', context)


@dpa_required
def dpa_leave_principal_approve(request, leave_id):
    """Principal final approval of a leave request."""
    if request.method != 'POST':
        return redirect('dpa_leave_detail', leave_id=leave_id)

    if request.user.role != Role.PRINCIPAL:
        return HttpResponseForbidden("Only the Principal can perform this action.")

    leave = get_object_or_404(LeaveRequest, pk=leave_id, school=request.user.school)
    leave.principal_approved_by = request.user
    leave.principal_approved_at = timezone.now()
    leave.principal_comment = request.POST.get('comment', '').strip()
    leave.status = LeaveStatus.APPROVED
    leave.save(update_fields=['principal_approved_by', 'principal_approved_at',
                              'principal_comment', 'status', 'updated_at'])
    messages.success(request, 'Leave finally approved.')
    return redirect('dpa_leave_detail', leave_id=leave.id)


# ==========================================================
# STAFF MOVEMENT LOG
# ==========================================================

@dpa_required
def dpa_staff_movement(request):
    """Staff in/out movement log for a chosen date."""
    selected_date_str = request.GET.get('date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else timezone.localdate()

    movements = StaffMovement.objects.filter(
        school=request.user.school,
        movement_date=selected_date,
    ).select_related('staff', 'recorded_by').order_by('-created_at')

    context = {
        'school': request.user.school,
        'selected_date': selected_date,
        'movements': movements,
        'total': movements.count(),
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
    }
    return render(request, 'dashboards/dpa/staff_movement.html', context)


@dpa_required
def dpa_staff_movement_create(request):
    """Log a staff movement."""
    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        direction = request.POST.get('direction')
        reason = request.POST.get('reason', '').strip()
        expected_return = request.POST.get('expected_return') or None

        if not staff_id or not direction:
            messages.error(request, 'Staff and direction are required.')
        else:
            StaffMovement.objects.create(
                school=request.user.school,
                staff_id=staff_id,
                direction=direction,
                movement_date=timezone.localdate(),
                reason=reason,
                expected_return_time=expected_return,
                recorded_by=request.user,
            )
            messages.success(request, 'Movement logged.')
            return redirect('dpa_staff_movement')

    context = {
        'school': request.user.school,
        'staff_list': _school_staff(request),
        'today': timezone.localdate(),
    }
    return render(request, 'dashboards/dpa/staff_movement_form.html', context)



# ==========================================================
# STAFF DIRECTORY
# ==========================================================

@dpa_required
def dpa_staff_directory(request):
    """Searchable staff directory with employment info."""
    from apps.accounts.models import User
    from apps.accounts.roles import Role

    qs = User.objects.filter(
        school=request.user.school,
        is_active=True,
    ).exclude(
        role__in=[Role.STUDENT, Role.PARENT, Role.SUPER_ADMIN]
    ).order_by('role', 'first_name', 'last_name')

    # Filters
    q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    employer_filter = request.GET.get('employer', '').strip()

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(employment_number__icontains=q)
            | Q(tsc_number__icontains=q)
        )
    if role_filter:
        qs = qs.filter(role=role_filter)
    if employer_filter:
        qs = qs.filter(employer_type=employer_filter)

    # Stats
    total_staff = User.objects.filter(
        school=request.user.school, is_active=True,
    ).exclude(role__in=[Role.STUDENT, Role.PARENT, Role.SUPER_ADMIN]).count()

    stats = {
        'total': total_staff,
        'teachers': qs.filter(role__in=[Role.TEACHER, Role.CLASS_TEACHER]).count(),
        'tsc': qs.filter(employer_type='tsc').count(),
        'bom': qs.filter(employer_type='bom').count(),
    }

    # Build role choices limited to staff roles
    from apps.accounts.roles import SCHOOL_STAFF
    role_choices = [
        (r.value, r.label) for r in SCHOOL_STAFF
    ]

    context = {
        'school': request.user.school,
        'staff_list': qs,
        'total': qs.count(),
        'stats': stats,
        'search': q,
        'role_filter': role_filter,
        'employer_filter': employer_filter,
        'role_choices': role_choices,
        'employer_choices': User.EmployerType.choices,
    }
    return render(request, 'dashboards/dpa/staff_directory.html', context)


@dpa_required
def dpa_staff_detail(request, user_id):
    """Staff profile — details, duties, leave, movements."""
    from apps.accounts.models import User

    staff = get_object_or_404(
        User, pk=user_id, school=request.user.school,
    )

    recent_duties = DutyRoster.objects.filter(
        school=request.user.school, staff=staff,
    ).order_by('-duty_date')[:10]

    recent_leave = LeaveRequest.objects.filter(
        school=request.user.school, staff=staff,
    ).order_by('-requested_at')[:10]

    recent_movements = StaffMovement.objects.filter(
        school=request.user.school, staff=staff,
    ).order_by('-movement_date', '-movement_time')[:10]

    recent_attendance = StaffAttendance.objects.filter(
        school=request.user.school, staff=staff,
    ).order_by('-date')[:30]

    context = {
        'school': request.user.school,
        'staff': staff,
        'recent_duties': recent_duties,
        'recent_leave': recent_leave,
        'recent_movements': recent_movements,
        'recent_attendance': recent_attendance,
    }
    return render(request, 'dashboards/dpa/staff_detail.html', context)



# ==========================================================
# STUDENT ADMINISTRATION
# ==========================================================

from apps.students.models import (
    Student, StudentMovement, StudentAdminCase,
    StudentMovementDirection, StudentMovementReason,
    AdminCaseType, AdminCaseStatus, AdminCasePriority,
)
from apps.attendance.models import Attendance


@dpa_required
def dpa_student_attendance(request):
    """Attendance overview by class for a chosen date."""
    from apps.academics.models import ClassLevel

    selected_date_str = request.GET.get('date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else timezone.localdate()

    school = request.user.school

    # Get all classes with students
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # Build per-class summary
    rows = []
    for cls in classes:
        students_in_class = Student.objects.for_user(request.user).filter(
            class_level=cls.name, is_active=True,
        )
        student_count = students_in_class.count()
        if student_count == 0:
            continue

        student_ids = list(students_in_class.values_list('id', flat=True))
        attendance_today = Attendance.objects.filter(
            student_id__in=student_ids,
            date=selected_date,
        )

        present = attendance_today.filter(status='present').count()
        absent = attendance_today.filter(status='absent').count()
        late = attendance_today.filter(status='late').count()
        recorded = attendance_today.count()

        rows.append({
            'class_level': cls.name,
            'students': student_count,
            'recorded': recorded,
            'present': present,
            'absent': absent,
            'late': late,
            'coverage': round((recorded / student_count) * 100) if student_count else 0,
        })

    total_students = sum(r['students'] for r in rows)
    total_present = sum(r['present'] for r in rows)
    total_absent = sum(r['absent'] for r in rows)
    total_late = sum(r['late'] for r in rows)

    context = {
        'school': school,
        'selected_date': selected_date,
        'rows': rows,
        'total_students': total_students,
        'total_present': total_present,
        'total_absent': total_absent,
        'total_late': total_late,
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
        'attendance_recorded': sum(r['recorded'] for r in rows),
    }
    return render(request, 'dashboards/dpa/student_attendance.html', context)


@dpa_required
def dpa_student_attendance_class(request, class_level):
    """Per-student attendance for one class on one date."""
    selected_date_str = request.GET.get('date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else timezone.localdate()

    students = Student.objects.for_user(request.user).filter(
        class_level=class_level, is_active=True,
    ).order_by('first_name', 'last_name')

    attendance_map = {
        a.student_id: a
        for a in Attendance.objects.filter(
            student__in=students, date=selected_date,
        )
    }

    rows = []
    present_count = absent_count = late_count = 0
    for s in students:
        a = attendance_map.get(s.id)
        status = a.status if a else '—'
        if status == 'present':
            present_count += 1
        elif status == 'absent':
            absent_count += 1
        elif status == 'late':
            late_count += 1

        rows.append({
            'student': s,
            'attendance': a,
            'status': status,
            'check_in': getattr(a, 'check_in_time', None) if a else None,
        })

    context = {
        'school': request.user.school,
        'class_level': class_level,
        'selected_date': selected_date,
        'rows': rows,
        'total': len(rows),
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
    }
    return render(request, 'dashboards/dpa/student_attendance_class.html', context)

@dpa_required
def dpa_student_movement_create(request):
    """Log a student movement."""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        direction = request.POST.get('direction')
        reason = request.POST.get('reason')
        reason_notes = request.POST.get('reason_notes', '').strip()
        expected_return = request.POST.get('expected_return') or None
        notify_guardian = request.POST.get('notify_guardian') == 'on'

        if not all([student_id, direction, reason]):
            messages.error(request, 'Student, direction, and reason are required.')
        else:
            try:
                student = Student.objects.for_user(request.user).get(pk=student_id)
                movement = StudentMovement.objects.create(
                    school=request.user.school,
                    student=student,
                    direction=direction,
                    movement_date=timezone.localdate(),
                    reason=reason,
                    reason_notes=reason_notes,
                    expected_return_time=expected_return,
                    authorized_by=request.user,
                    released_by=request.user,
                    guardian_notified=notify_guardian,
                    guardian_notified_at=timezone.now() if notify_guardian else None,
                )
                messages.success(request, f"Movement logged for {student.first_name}.")
                return redirect('dpa_student_movement')
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')

    students = Student.objects.for_user(request.user).filter(
        is_active=True
    ).order_by('class_level', 'first_name', 'last_name')[:500]

    context = {
        'school': request.user.school,
        'students': students,
        'directions': StudentMovementDirection.choices,
        'reasons': StudentMovementReason.choices,
    }
    return render(request, 'dashboards/dpa/student_movement_form.html', context)


@dpa_required
def dpa_student_movement_return(request, movement_id):
    """Mark a student as returned (creates the paired IN entry)."""
    if request.method != 'POST':
        return redirect('dpa_student_movement')

    out = get_object_or_404(
        StudentMovement, pk=movement_id, school=request.user.school,
        direction=StudentMovementDirection.OUT,
    )
    now = timezone.localtime().time()
    out.actual_return_time = now
    out.save(update_fields=['actual_return_time'])

    StudentMovement.objects.create(
        school=request.user.school,
        student=out.student,
        direction=StudentMovementDirection.IN,
        movement_date=timezone.localdate(),
        reason=out.reason,
        reason_notes=f"Return logged against movement #{out.id}",
        authorized_by=request.user,
        released_by=request.user,
    )
    messages.success(request, f"{out.student.first_name} marked as returned.")
    return redirect('dpa_student_movement')


# ---------- ADMIN CASES ----------

@dpa_required
def dpa_admin_cases(request):
    """List of student administrative cases."""
    qs = StudentAdminCase.objects.filter(
        school=request.user.school
    ).select_related('student', 'opened_by', 'assigned_to').order_by('-created_at')

    status = request.GET.get('status', '').strip()
    case_type = request.GET.get('type', '').strip()
    search = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if case_type:
        qs = qs.filter(case_type=case_type)
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    open_count = qs.filter(status__in=[AdminCaseStatus.OPEN, AdminCaseStatus.IN_REVIEW]).count()
    urgent_count = qs.filter(priority=AdminCasePriority.URGENT).count()
    resolved_count = qs.filter(status=AdminCaseStatus.RESOLVED).count()

    context = {
        'school': request.user.school,
        'cases': qs[:200],
        'total': qs.count(),
        'open_count': open_count,
        'urgent_count': urgent_count,
        'resolved_count': resolved_count,
        'status_filter': status,
        'type_filter': case_type,
        'search': search,
        'status_choices': AdminCaseStatus.choices,
        'type_choices': AdminCaseType.choices,
    }
    return render(request, 'dashboards/dpa/admin_cases.html', context)


@dpa_required
def dpa_admin_case_create(request):
    """Create a new admin case."""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        case_type = request.POST.get('case_type')
        priority = request.POST.get('priority', 'normal')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()

        if not all([student_id, case_type, title, description]):
            messages.error(request, 'All fields are required.')
        else:
            try:
                student = Student.objects.for_user(request.user).get(pk=student_id)
                case = StudentAdminCase.objects.create(
                    school=request.user.school,
                    student=student,
                    case_type=case_type,
                    priority=priority,
                    title=title,
                    description=description,
                    opened_by=request.user,
                    assigned_to=request.user,
                )
                messages.success(request, f"Case opened for {student.first_name}.")
                return redirect('dpa_admin_case_detail', case_id=case.id)
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')

    students = Student.objects.for_user(request.user).filter(
        is_active=True
    ).order_by('class_level', 'first_name', 'last_name')[:500]

    context = {
        'school': request.user.school,
        'students': students,
        'case_types': AdminCaseType.choices,
        'priorities': AdminCasePriority.choices,
    }
    return render(request, 'dashboards/dpa/admin_case_form.html', context)


@dpa_required
def dpa_admin_case_detail(request, case_id):
    """Detail view of one admin case."""
    case = get_object_or_404(
        StudentAdminCase.objects.select_related('student', 'opened_by', 'assigned_to', 'resolved_by'),
        pk=case_id, school=request.user.school,
    )

    context = {
        'school': request.user.school,
        'case': case,
        'can_edit': request.user.role in (Role.DEPUTY_ADMIN, Role.PRINCIPAL),
        'status_choices': AdminCaseStatus.choices,
    }
    return render(request, 'dashboards/dpa/admin_case_detail.html', context)


@dpa_required
def dpa_admin_case_update(request, case_id):
    """Update status/resolution of an admin case."""
    if request.method != 'POST':
        return redirect('dpa_admin_case_detail', case_id=case_id)

    case = get_object_or_404(StudentAdminCase, pk=case_id, school=request.user.school)
    new_status = request.POST.get('status', case.status)
    notes = request.POST.get('resolution_notes', '').strip()

    case.status = new_status
    if notes:
        case.resolution_notes = (case.resolution_notes + '\n\n' + notes).strip() if case.resolution_notes else notes

    if new_status == AdminCaseStatus.RESOLVED:
        case.resolved_by = request.user
        case.resolved_at = timezone.now()

    case.save()
    messages.success(request, 'Case updated.')
    return redirect('dpa_admin_case_detail', case_id=case.id)



# ==========================================================
# DUTY ROSTER PDF
# ==========================================================

@dpa_required
def dpa_duty_roster_pdf(request):
    """Generate PDF of the duty roster for a period — grouped by staff."""
    anchor_str = request.GET.get('week', '')
    anchor = parse_date(anchor_str) if anchor_str else timezone.localdate()

    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=6)

    duties = DutyRoster.objects.filter(
        school=request.user.school,
        duty_date__gte=week_start,
        duty_date__lte=week_end,
    ).select_related('staff', 'assigned_by').order_by('staff__first_name', 'duty_date')

    # Group by staff — one row per staff+duty_type
    grouped = {}
    for d in duties:
        key = (d.staff_id, d.duty_type)
        if key not in grouped:
            grouped[key] = {
                'staff': d.staff,
                'duty_type': d.duty_type,
                'duty_type_display': d.get_duty_type_display(),
                'dates': [],
                'start_time': d.start_time,
                'end_time': d.end_time,
                'location': d.location,
                'completed_count': 0,
                'total_count': 0,
            }
        grouped[key]['dates'].append(d.duty_date)
        grouped[key]['total_count'] += 1
        if d.completed:
            grouped[key]['completed_count'] += 1
        # Prefer earliest start time
        if d.start_time and (grouped[key]['start_time'] is None or d.start_time < grouped[key]['start_time']):
            grouped[key]['start_time'] = d.start_time

    rows = []
    for g in grouped.values():
        g['dates'].sort()
        g['date_from'] = g['dates'][0]
        g['date_to'] = g['dates'][-1]
        g['day_count'] = len(g['dates'])
        # Format period label
        if g['date_from'] == g['date_to']:
            g['period'] = g['date_from'].strftime('%d %b %Y')
        elif g['date_from'].month == g['date_to'].month and g['date_from'].year == g['date_to'].year:
            g['period'] = f"{g['date_from'].strftime('%d')} – {g['date_to'].strftime('%d %b %Y')}"
        else:
            g['period'] = f"{g['date_from'].strftime('%d %b')} – {g['date_to'].strftime('%d %b %Y')}"
        rows.append(g)

    # Sort rows by staff name
    rows.sort(key=lambda r: ((r['staff'].first_name or '').lower(), (r['staff'].last_name or '').lower()))

    html_string = render_to_string('pdf/dpa_duty_roster.html',
        build_pdf_context(
            school=request.user.school,
            generated_by=request.user,
            week_start=week_start,
            week_end=week_end,
            rows=rows,
            total_duties=duties.count(),
            unique_staff=len(set(d.staff_id for d in duties)),
        )
    )

    filename = f"duty_roster_{week_start.strftime('%Y%m%d')}.pdf"
    return html_to_pdf_response(html_string, filename)



@dpa_required
def dpa_student_movement(request):
    """Student movement log for a chosen date."""
    selected_date_str = request.GET.get('date', '')
    selected_date = parse_date(selected_date_str) if selected_date_str else timezone.localdate()

    movements = StudentMovement.objects.filter(
        school=request.user.school,
        movement_date=selected_date,
    ).select_related('student', 'authorized_by', 'released_by').order_by('-movement_time')

    out_count = movements.filter(direction=StudentMovementDirection.OUT).count()
    in_count = movements.filter(direction=StudentMovementDirection.IN).count()
    still_out = movements.filter(
        direction=StudentMovementDirection.OUT,
        actual_return_time__isnull=True,
    ).count()

    context = {
        'school': request.user.school,
        'selected_date': selected_date,
        'movements': movements,
        'out_count': out_count,
        'in_count': in_count,
        'still_out': still_out,
        'total': movements.count(),
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
    }
    return render(request, 'dashboards/dpa/student_movement.html', context)



# ==========================================================
# LEAVE-OUT PDF
# ==========================================================

@dpa_required
def dpa_leave_out_pdf(request, leave_out_id):
    """Generate professional PDF for a single leave-out / suspension."""
    leave = get_object_or_404(
        StudentLeaveOut.objects.select_related(
            'student', 'discipline_record', 'requested_by',
            'dpa_approved_by', 'principal_approved_by',
        ),
        pk=leave_out_id, school=request.user.school,
    )

    html_string = render_to_string('pdf/dpa_leave_out.html',
        build_pdf_context(
            school=request.user.school,
            generated_by=request.user,
            leave=leave,
        )
    )


    filename = f"leave_out_{leave.id}_{leave.student.admission_number or 'student'}.pdf"
    return html_to_pdf_response(html_string, filename)