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