"""
Deputy Principal — Academics dashboard views.

Focus: coordination and approvals for teaching, exams, and curriculum.
Analytics belong to the Director of Studies module.
"""
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Avg

from apps.accounts.roles import Role
from apps.academics.models import (
    ClassLevel, Subject, Timetable,
    SyllabusCoverage, CoverageStatus,
    LessonPlan, LessonPlanStatus,
    RemedialClass, RemedialStatus,
)
from apps.grades.models import Exam, Grade, MarkSheet, MarkSheetStatus
from apps.teachers.models import Teacher, TeachingObservation


def dpa_acad_required(view_func):
    """Restrict view to DPA Academics, Principal, or Super Admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
        if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL, Role.SUPER_ADMIN):
            return HttpResponseForbidden("You do not have access to this page.")
        if request.user.school is None:
            return HttpResponseForbidden("Your account is not linked to a school.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ==========================================================
# MAIN DASHBOARD
# ==========================================================

@dpa_acad_required
def dpa_acad_dashboard(request):
    """DPA Academics landing page."""
    school = request.user.school
    today = timezone.localdate()

    # ---- Syllabus coverage KPIs ----
    current_year = today.year
    syllabus_qs = SyllabusCoverage.objects.filter(school=school, year=current_year)
    total_topics = syllabus_qs.count()
    completed_topics = syllabus_qs.filter(status=CoverageStatus.COMPLETED).count()
    behind_topics = syllabus_qs.filter(status=CoverageStatus.BEHIND).count()
    in_progress = syllabus_qs.filter(status=CoverageStatus.IN_PROGRESS).count()

    coverage_percent = round((completed_topics / total_topics) * 100) if total_topics else 0

    syllabus_stats = {
        'total': total_topics,
        'completed': completed_topics,
        'in_progress': in_progress,
        'behind': behind_topics,
        'percent': coverage_percent,
    }

    # ---- Lesson plan queue ----
    pending_lesson_plans = LessonPlan.objects.filter(
        school=school, status=LessonPlanStatus.SUBMITTED,
    ).select_related('teacher', 'subject', 'class_level').order_by('week_ending')[:5]

    lesson_plan_stats = {
        'submitted': LessonPlan.objects.filter(
            school=school, status=LessonPlanStatus.SUBMITTED,
        ).count(),
        'approved_this_month': LessonPlan.objects.filter(
            school=school,
            status=LessonPlanStatus.APPROVED,
            reviewed_at__gte=today.replace(day=1),
        ).count(),
    }

    # ---- Mark sheet queue ----
    pending_mark_sheets = MarkSheet.objects.filter(
        school=school, status=MarkSheetStatus.SUBMITTED,
    ).select_related('exam', 'subject', 'class_level', 'teacher').order_by('-submitted_at')[:5]

    mark_sheet_stats = {
        'submitted': MarkSheet.objects.filter(
            school=school, status=MarkSheetStatus.SUBMITTED,
        ).count(),
        'published_this_month': MarkSheet.objects.filter(
            school=school,
            status=MarkSheetStatus.PUBLISHED,
            published_at__gte=today.replace(day=1),
        ).count(),
    }

    # ---- Upcoming exams ----
    upcoming_exams = Exam.objects.filter(
        school=school, date__gte=today,
    ).order_by('date')[:5]

    # ---- Recently completed exams (waiting for mark sheets) ----
    recent_exams = Exam.objects.filter(
        school=school, date__lt=today,
    ).order_by('-date')[:5]

    # ---- Remedial classes ----
    upcoming_remedial = RemedialClass.objects.filter(
        school=school,
        scheduled_date__gte=today,
        status__in=[RemedialStatus.SCHEDULED, RemedialStatus.ONGOING],
    ).select_related('subject', 'class_level', 'teacher').order_by('scheduled_date')[:5]

    remedial_stats = {
        'upcoming': RemedialClass.objects.filter(
            school=school,
            scheduled_date__gte=today,
            status__in=[RemedialStatus.SCHEDULED, RemedialStatus.ONGOING],
        ).count(),
        'this_week': RemedialClass.objects.filter(
            school=school,
            scheduled_date__gte=today,
            scheduled_date__lte=today + timedelta(days=7),
        ).count(),
    }

    # ---- Teachers ----
    teacher_count = Teacher.objects.filter(school=school, is_active=True).count()
    observations_this_term = TeachingObservation.objects.filter(
        school=school,
        observed_on__gte=today.replace(day=1),
    ).count()

    context = {
        'school': school,
        'today': today,
        'syllabus_stats': syllabus_stats,
        'pending_lesson_plans': pending_lesson_plans,
        'lesson_plan_stats': lesson_plan_stats,
        'pending_mark_sheets': pending_mark_sheets,
        'mark_sheet_stats': mark_sheet_stats,
        'upcoming_exams': upcoming_exams,
        'recent_exams': recent_exams,
        'upcoming_remedial': upcoming_remedial,
        'remedial_stats': remedial_stats,
        'teacher_count': teacher_count,
        'observations_this_term': observations_this_term,
    }
    return render(request, 'dashboards/dpa_acad/dashboard.html', context)