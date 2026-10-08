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

from apps.accounts.roles import Role
from apps.discipline.models import (
    DisciplineRecord, DisciplineAction,
    DisciplineCategory, DisciplineSeverity, DisciplineStatus,
    StudentLeaveOut, LeaveOutType, LeaveOutStatus, SuspensionReason,
)
from apps.staff.models import (
    LeaveRequest, DutyRoster, StaffAttendance,
    LeaveType, LeaveStatus,
    DutyType, StaffAttendanceStatus,
)


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

    html_string = render_to_string(template, {
        'school': school,
        'report': report,
        'scope_desc': scope_desc,
        'period': period,
        'generated_by': request.user,
        'generated_on': timezone.now(),
        'date_from': date_from,
        'date_to': date_to,
        'grade': grade,
        'class_level': class_level,
    })

    filename = f"discipline_{filename_scope}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    return html_to_pdf_response(html_string, filename)