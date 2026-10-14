"""
Deputy Principal — Academics dashboard views.

Focus: coordination and approvals for teaching, exams, and curriculum.
Analytics belong to the Director of Studies module.
"""
from datetime import timedelta
from functools import wraps
from django.http import JsonResponse

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
    StreamSubjectTeacher,
)
from apps.grades.models import Exam, Grade, MarkSheet, MarkSheetStatus
from apps.teachers.models import Teacher, TeachingObservation
from apps.core.pdf_utils import build_pdf_context


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
  
  

# ==========================================================
# EXAMS
# ==========================================================

@dpa_acad_required
def dpa_acad_exams(request):
    """List of all exams — past, current, upcoming."""
    school = request.user.school
    today = timezone.localdate()

    qs = Exam.objects.filter(school=school).order_by('-date')

    # Filters
    term = request.GET.get('term', '').strip()
    year = request.GET.get('year', '').strip()
    tab = request.GET.get('tab', 'upcoming')

    if term:
        qs = qs.filter(term=term)
    if year:
        qs = qs.filter(year=year)

    # Split into upcoming/past
    if tab == 'upcoming':
        filtered_qs = qs.filter(date__gte=today)
    elif tab == 'past':
        filtered_qs = qs.filter(date__lt=today)
    else:
        filtered_qs = qs

    # Term + year choices from data
    terms = Exam.objects.filter(school=school).values_list('term', flat=True).distinct().order_by('term')
    years = Exam.objects.filter(school=school).values_list('year', flat=True).distinct().order_by('-year')

    # Attach mark sheet summary per exam
    exams_with_summary = []
    for exam in filtered_qs[:100]:
        sheets = exam.mark_sheets.all()
        total = sheets.count()
        published = sheets.filter(status=MarkSheetStatus.PUBLISHED).count()
        approved = sheets.filter(status=MarkSheetStatus.APPROVED).count()
        submitted = sheets.filter(status=MarkSheetStatus.SUBMITTED).count()
        exams_with_summary.append({
            'exam': exam,
            'total_sheets': total,
            'published': published,
            'approved': approved,
            'submitted': submitted,
            'progress': round(((published + approved) / total) * 100) if total else 0,
        })

    context = {
        'school': school,
        'today': today,
        'exams': exams_with_summary,
        'total': filtered_qs.count(),
        'tab': tab,
        'term_filter': term,
        'year_filter': year,
        'terms': [t for t in terms if t],
        'years': [y for y in years if y],
    }
    return render(request, 'dashboards/dpa_acad/exams.html', context)


@dpa_acad_required
def dpa_acad_exam_detail(request, exam_id):
    """Exam overview — all mark sheets for this exam."""
    school = request.user.school
    exam = get_object_or_404(Exam, pk=exam_id, school=school)

    sheets = exam.mark_sheets.select_related(
        'class_level', 'subject', 'teacher'
    ).order_by('class_level__order', 'subject__name')

    # Group by class
    by_class = {}
    for sheet in sheets:
        cls_name = sheet.class_level.name if sheet.class_level else 'No class'
        by_class.setdefault(cls_name, []).append(sheet)

    # Status counts
    status_counts = {
        'draft': sheets.filter(status=MarkSheetStatus.DRAFT).count(),
        'submitted': sheets.filter(status=MarkSheetStatus.SUBMITTED).count(),
        'approved': sheets.filter(status=MarkSheetStatus.APPROVED).count(),
        'published': sheets.filter(status=MarkSheetStatus.PUBLISHED).count(),
        'rejected': sheets.filter(status=MarkSheetStatus.REJECTED).count(),
    }

    context = {
        'school': school,
        'exam': exam,
        'by_class': by_class,
        'total_sheets': sheets.count(),
        'status_counts': status_counts,
    }
    return render(request, 'dashboards/dpa_acad/exam_detail.html', context)


# ==========================================================
# MARK SHEETS
# ==========================================================

@dpa_acad_required
def dpa_acad_mark_sheets(request):
    """Queue of mark sheets for review."""
    school = request.user.school

    qs = MarkSheet.objects.filter(school=school).select_related(
        'exam', 'class_level', 'subject', 'teacher'
    ).order_by('-exam__date', 'class_level__order', 'subject__name')

    status = request.GET.get('status', '').strip()
    exam_filter = request.GET.get('exam', '').strip()

    if status:
        qs = qs.filter(status=status)
    if exam_filter:
        qs = qs.filter(exam_id=exam_filter)

    # Status counts (always across all sheets for the school)
    all_sheets = MarkSheet.objects.filter(school=school)

    context = {
        'school': school,
        'sheets': qs[:200],
        'total': qs.count(),
        'status_filter': status,
        'exam_filter': exam_filter,
        'status_choices': MarkSheetStatus.choices,
        'exams': Exam.objects.filter(school=school).order_by('-date')[:30],
        'pending_count': all_sheets.filter(status=MarkSheetStatus.SUBMITTED).count(),
        'approved_count': all_sheets.filter(status=MarkSheetStatus.APPROVED).count(),
        'published_count': all_sheets.filter(status=MarkSheetStatus.PUBLISHED).count(),
        'draft_count': all_sheets.filter(status=MarkSheetStatus.DRAFT).count(),
    }
    return render(request, 'dashboards/dpa_acad/mark_sheets.html', context)


@dpa_acad_required
def dpa_acad_mark_sheet_detail(request, sheet_id):
    """View and approve/reject a single mark sheet."""
    school = request.user.school
    sheet = get_object_or_404(
        MarkSheet.objects.select_related('exam', 'class_level', 'subject', 'teacher'),
        pk=sheet_id, school=school,
    )

    # All grades for this exam+class+subject
    grades = Grade.objects.filter(
        exam=sheet.exam,
        student__class_level=sheet.class_level.name if sheet.class_level else '',
        subject=sheet.subject,
    ).select_related('student').order_by('student__first_name')

    # Stats
    if grades:
        marks = [g.marks for g in grades if g.marks is not None]
        if marks:
            avg = round(sum(marks) / len(marks), 1)
            highest = max(marks)
            lowest = min(marks)
            pass_count = sum(1 for m in marks if m >= (grades[0].out_of * 0.5 if grades[0].out_of else 50))
        else:
            avg = highest = lowest = pass_count = 0
    else:
        avg = highest = lowest = pass_count = 0

    stats = {
        'total': len(grades),
        'average': avg,
        'highest': highest,
        'lowest': lowest,
        'pass_count': pass_count,
        'pass_rate': round((pass_count / len(grades)) * 100) if grades else 0,
    }

    context = {
        'school': school,
        'sheet': sheet,
        'grades': grades,
        'stats': stats,
        'can_approve': request.user.role in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL),
    }
    return render(request, 'dashboards/dpa_acad/mark_sheet_detail.html', context)


@dpa_acad_required
def dpa_acad_mark_sheet_approve(request, sheet_id):
    """Approve a submitted mark sheet."""
    if request.method != 'POST':
        return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet_id)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot approve mark sheets.")

    sheet = get_object_or_404(MarkSheet, pk=sheet_id, school=request.user.school)
    sheet.status = MarkSheetStatus.APPROVED
    sheet.reviewed_by = request.user
    sheet.reviewed_at = timezone.now()
    sheet.review_comment = request.POST.get('comment', '').strip()
    sheet.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment', 'updated_at'])

    messages.success(request, f'Mark sheet approved: {sheet.exam.name} · {sheet.subject.name} · {sheet.class_level.name}.')
    return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet.id)


@dpa_acad_required
def dpa_acad_mark_sheet_reject(request, sheet_id):
    """Reject a submitted mark sheet back to the teacher."""
    if request.method != 'POST':
        return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet_id)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot reject mark sheets.")

    sheet = get_object_or_404(MarkSheet, pk=sheet_id, school=request.user.school)
    sheet.status = MarkSheetStatus.REJECTED
    sheet.reviewed_by = request.user
    sheet.reviewed_at = timezone.now()
    sheet.review_comment = request.POST.get('comment', '').strip()
    sheet.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment', 'updated_at'])

    messages.warning(request, f'Mark sheet sent back for revision.')
    return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet.id)


@dpa_acad_required
def dpa_acad_mark_sheet_publish(request, sheet_id):
    """Publish an approved mark sheet — results become visible to students/parents."""
    if request.method != 'POST':
        return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet_id)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot publish mark sheets.")

    sheet = get_object_or_404(MarkSheet, pk=sheet_id, school=request.user.school)

    if sheet.status != MarkSheetStatus.APPROVED:
        messages.error(request, 'Only approved mark sheets can be published.')
        return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet.id)

    sheet.status = MarkSheetStatus.PUBLISHED
    sheet.published_at = timezone.now()
    sheet.published_by = request.user
    sheet.save(update_fields=['status', 'published_at', 'published_by', 'updated_at'])

    messages.success(request, 'Mark sheet published. Results are now visible.')
    return redirect('dpa_acad_mark_sheet_detail', sheet_id=sheet.id)
  
  

# ==========================================================
# SYLLABUS COVERAGE
# ==========================================================

@dpa_acad_required
def dpa_acad_syllabus(request):
    """Syllabus coverage tracker — by class, subject, teacher."""
    school = request.user.school
    today = timezone.localdate()

    qs = SyllabusCoverage.objects.filter(school=school).select_related(
        'class_level', 'subject', 'teacher',
    ).order_by('class_level__order', 'subject__name', 'planned_week', 'topic')

    class_filter = request.GET.get('class', '').strip()
    subject_filter = request.GET.get('subject', '').strip()
    status_filter = request.GET.get('status', '').strip()
    year_filter = request.GET.get('year', str(today.year)).strip()
    term_filter = request.GET.get('term', '').strip()

    if class_filter:
        qs = qs.filter(class_level_id=class_filter)
    if subject_filter:
        qs = qs.filter(subject_id=subject_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if year_filter:
        try:
            qs = qs.filter(year=int(year_filter))
        except ValueError:
            pass
    if term_filter:
        qs = qs.filter(term=term_filter)

    # Status counts across the full school (unfiltered by class/subject)
    base_qs = SyllabusCoverage.objects.filter(school=school)
    if year_filter:
        try:
            base_qs = base_qs.filter(year=int(year_filter))
        except ValueError:
            pass

    status_counts = {
        'not_started': base_qs.filter(status=CoverageStatus.NOT_STARTED).count(),
        'in_progress': base_qs.filter(status=CoverageStatus.IN_PROGRESS).count(),
        'completed': base_qs.filter(status=CoverageStatus.COMPLETED).count(),
        'behind': base_qs.filter(status=CoverageStatus.BEHIND).count(),
    }
    total = sum(status_counts.values())
    overall_percent = round((status_counts['completed'] / total) * 100) if total else 0

    # Group by class + subject
    grouped = {}
    for item in qs[:500]:
        key = (item.class_level.name if item.class_level else 'No class',
               item.subject.name if item.subject else 'No subject')
        grouped.setdefault(key, {
            'class_name': key[0],
            'subject_name': key[1],
            'teacher': item.teacher,
            'items': [],
            'completed': 0,
            'in_progress': 0,
            'behind': 0,
            'not_started': 0,
        })
        grouped[key]['items'].append(item)
        if item.status == CoverageStatus.COMPLETED:
            grouped[key]['completed'] += 1
        elif item.status == CoverageStatus.IN_PROGRESS:
            grouped[key]['in_progress'] += 1
        elif item.status == CoverageStatus.BEHIND:
            grouped[key]['behind'] += 1
        else:
            grouped[key]['not_started'] += 1

    # Compute per-group percentage
    for g in grouped.values():
        total_g = len(g['items'])
        g['percent'] = round((g['completed'] / total_g) * 100) if total_g else 0
        g['total'] = total_g

    context = {
        'school': school,
        'today': today,
        'grouped': grouped,
        'total': qs.count(),
        'status_counts': status_counts,
        'overall_percent': overall_percent,
        'class_filter': class_filter,
        'subject_filter': subject_filter,
        'status_filter': status_filter,
        'year_filter': year_filter,
        'term_filter': term_filter,
        'classes': ClassLevel.objects.filter(school=school).order_by('order', 'name'),
        'subjects': Subject.objects.filter(school=school).order_by('name'),
        'status_choices': CoverageStatus.choices,
    }
    return render(request, 'dashboards/dpa_acad/syllabus.html', context)


# ==========================================================
# LESSON PLANS
# ==========================================================

@dpa_acad_required
def dpa_acad_lesson_plans(request):
    """Queue of lesson plans for review."""
    school = request.user.school

    qs = LessonPlan.objects.filter(school=school).select_related(
        'teacher', 'class_level', 'subject', 'reviewed_by',
    ).order_by('-week_ending', 'teacher__first_name')

    status_filter = request.GET.get('status', '').strip()
    teacher_filter = request.GET.get('teacher', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if teacher_filter:
        qs = qs.filter(teacher_id=teacher_filter)

    all_plans = LessonPlan.objects.filter(school=school)

    context = {
        'school': school,
        'plans': qs[:200],
        'total': qs.count(),
        'status_filter': status_filter,
        'teacher_filter': teacher_filter,
        'status_choices': LessonPlanStatus.choices,
        'teachers': Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name'),
        'submitted_count': all_plans.filter(status=LessonPlanStatus.SUBMITTED).count(),
        'approved_count': all_plans.filter(status=LessonPlanStatus.APPROVED).count(),
        'revision_count': all_plans.filter(status=LessonPlanStatus.REVISION).count(),
        'draft_count': all_plans.filter(status=LessonPlanStatus.DRAFT).count(),
    }
    return render(request, 'dashboards/dpa_acad/lesson_plans.html', context)


@dpa_acad_required
def dpa_acad_lesson_plan_detail(request, plan_id):
    """View a lesson plan and approve or request revision."""
    school = request.user.school
    plan = get_object_or_404(
        LessonPlan.objects.select_related('teacher', 'class_level', 'subject', 'reviewed_by'),
        pk=plan_id, school=school,
    )

    context = {
        'school': school,
        'plan': plan,
        'can_review': request.user.role in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL),
    }
    return render(request, 'dashboards/dpa_acad/lesson_plan_detail.html', context)


@dpa_acad_required
def dpa_acad_lesson_plan_approve(request, plan_id):
    """Approve a lesson plan."""
    if request.method != 'POST':
        return redirect('dpa_acad_lesson_plan_detail', plan_id=plan_id)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot approve lesson plans.")

    plan = get_object_or_404(LessonPlan, pk=plan_id, school=request.user.school)
    plan.status = LessonPlanStatus.APPROVED
    plan.reviewed_by = request.user
    plan.reviewed_at = timezone.now()
    plan.review_comment = request.POST.get('comment', '').strip()
    plan.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment', 'updated_at'])

    messages.success(request, f'Lesson plan approved.')
    return redirect('dpa_acad_lesson_plan_detail', plan_id=plan.id)


@dpa_acad_required
def dpa_acad_lesson_plan_revision(request, plan_id):
    """Return a lesson plan for revision."""
    if request.method != 'POST':
        return redirect('dpa_acad_lesson_plan_detail', plan_id=plan_id)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot return lesson plans.")

    plan = get_object_or_404(LessonPlan, pk=plan_id, school=request.user.school)
    plan.status = LessonPlanStatus.REVISION
    plan.reviewed_by = request.user
    plan.reviewed_at = timezone.now()
    plan.review_comment = request.POST.get('comment', '').strip()
    plan.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_comment', 'updated_at'])

    messages.warning(request, 'Lesson plan returned for revision.')
    return redirect('dpa_acad_lesson_plan_detail', plan_id=plan.id)


# ==========================================================
# SUBJECT ALLOCATION
# ==========================================================

@dpa_acad_required
def dpa_acad_subject_allocation(request):
    """Assign teachers to subjects per class."""
    school = request.user.school

    class_filter = request.GET.get('class', '').strip()

    # Base data
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')

    # Timetable entries grouped by class
    timetable_qs = Timetable.objects.filter(school=school).select_related(
        'class_level', 'subject', 'teacher',
    ).order_by('class_level__order', 'subject__name', 'day_of_week', 'start_time')

    if class_filter:
        timetable_qs = timetable_qs.filter(class_level_id=class_filter)

    # Group by class → subject → entries
    allocation = {}
    for entry in timetable_qs:
        cls_name = entry.class_level.name if entry.class_level else 'No class'
        subj_name = entry.subject.name if entry.subject else 'No subject'
        key = (cls_name, subj_name)
        allocation.setdefault(key, {
            'class_name': cls_name,
            'subject_name': subj_name,
            'subject': entry.subject,
            'teacher': entry.teacher,
            'periods': [],
        })
        allocation[key]['periods'].append(entry)

    # Attach teacher if missing
    for key, val in allocation.items():
        if val['teacher'] is None and val['subject']:
            # Fallback to Subject.teacher
            val['teacher'] = val['subject'].teacher

    # Sort by class then subject
    sorted_alloc = sorted(allocation.values(), key=lambda x: (x['class_name'], x['subject_name']))

    # Stats
    total_classes = classes.count()
    total_subjects = Subject.objects.filter(school=school).count()
    total_allocations = len(sorted_alloc)
    unassigned = sum(1 for a in sorted_alloc if a['teacher'] is None)

    context = {
        'school': school,
        'classes': classes,
        'teachers': teachers,
        'allocations': sorted_alloc,
        'class_filter': class_filter,
        'total_classes': total_classes,
        'total_subjects': total_subjects,
        'total_allocations': total_allocations,
        'unassigned': unassigned,
    }
    return render(request, 'dashboards/dpa_acad/subject_allocation.html', context)


@dpa_acad_required
def dpa_acad_subject_assign(request, subject_id):
    """Assign or reassign a teacher to a subject."""
    if request.method != 'POST':
        return redirect('dpa_acad_subject_allocation')

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return HttpResponseForbidden("You cannot assign subjects.")

    subject = get_object_or_404(Subject, pk=subject_id, school=request.user.school)
    teacher_id = request.POST.get('teacher_id', '').strip()

    if teacher_id:
        try:
            teacher = Teacher.objects.get(pk=teacher_id, school=request.user.school)
            subject.teacher = teacher
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher not found.')
            return redirect('dpa_acad_subject_allocation')
    else:
        subject.teacher = None

    subject.save(update_fields=['teacher'])

    # Also update all timetable entries for this subject
    Timetable.objects.filter(subject=subject).update(teacher=subject.teacher)

    messages.success(request, f'{subject.name} assigned to {subject.teacher.first_name if subject.teacher else "no one"}.')
    return redirect('dpa_acad_subject_allocation')
  
  

# ==========================================================
# TEACHER PERFORMANCE
# ==========================================================

@dpa_acad_required
def dpa_acad_teachers(request):
    """Teacher performance overview — syllabus, mark sheets, observations."""
    school = request.user.school

    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')

    # Build per-teacher stats
    teacher_rows = []
    for t in teachers:
        # Syllabus coverage
        coverage_qs = SyllabusCoverage.objects.filter(school=school, teacher=t)
        total_topics = coverage_qs.count()
        completed_topics = coverage_qs.filter(status=CoverageStatus.COMPLETED).count()
        behind_topics = coverage_qs.filter(status=CoverageStatus.BEHIND).count()
        coverage_percent = round((completed_topics / total_topics) * 100) if total_topics else 0

        # Mark sheets
        sheets = MarkSheet.objects.filter(school=school, teacher=t)
        total_sheets = sheets.count()
        published_sheets = sheets.filter(status=MarkSheetStatus.PUBLISHED).count()
        pending_sheets = sheets.filter(status=MarkSheetStatus.SUBMITTED).count()

        # Lesson plans
        plans = LessonPlan.objects.filter(school=school, teacher=t)
        submitted_plans = plans.filter(status=LessonPlanStatus.SUBMITTED).count()
        approved_plans = plans.filter(status=LessonPlanStatus.APPROVED).count()

        # Observations
        obs = TeachingObservation.objects.filter(school=school, teacher=t)
        obs_count = obs.count()
        # Calculate average of averages
        obs_avgs = [o.average_rating for o in obs if o.average_rating is not None]
        avg_observation = round(sum(obs_avgs) / len(obs_avgs), 1) if obs_avgs else None

        teacher_rows.append({
            'teacher': t,
            'total_topics': total_topics,
            'completed_topics': completed_topics,
            'behind_topics': behind_topics,
            'coverage_percent': coverage_percent,
            'total_sheets': total_sheets,
            'published_sheets': published_sheets,
            'pending_sheets': pending_sheets,
            'submitted_plans': submitted_plans,
            'approved_plans': approved_plans,
            'obs_count': obs_count,
            'avg_observation': avg_observation,
        })

    # Sort: behind schedule first (most critical), then by name
    teacher_rows.sort(key=lambda r: (-r['behind_topics'], r['teacher'].first_name))

    # Summary stats
    total_teachers = teachers.count()
    total_observations = TeachingObservation.objects.filter(school=school).count()
    overdue_reviews = (
        LessonPlan.objects.filter(school=school, status=LessonPlanStatus.SUBMITTED).count()
        + MarkSheet.objects.filter(school=school, status=MarkSheetStatus.SUBMITTED).count()
    )

    context = {
        'school': school,
        'teacher_rows': teacher_rows,
        'total_teachers': total_teachers,
        'total_observations': total_observations,
        'overdue_reviews': overdue_reviews,
    }
    return render(request, 'dashboards/dpa_acad/teachers.html', context)


@dpa_acad_required
def dpa_acad_teacher_detail(request, teacher_id):
    """Full teacher profile with all academic activity."""
    school = request.user.school
    teacher = get_object_or_404(Teacher, pk=teacher_id, school=school)

    # Recent observations
    observations = TeachingObservation.objects.filter(
        school=school, teacher=teacher,
    ).order_by('-observed_on')[:10]

    # Recent lesson plans
    lesson_plans = LessonPlan.objects.filter(
        school=school, teacher=teacher,
    ).order_by('-week_ending')[:10]

    # Recent mark sheets
    mark_sheets = MarkSheet.objects.filter(
        school=school, teacher=teacher,
    ).select_related('exam', 'subject', 'class_level').order_by('-exam__date')[:10]

    # Syllabus coverage summary
    coverage = SyllabusCoverage.objects.filter(
        school=school, teacher=teacher,
    ).select_related('class_level', 'subject')

    coverage_by_subject = {}
    for c in coverage:
        key = f"{c.class_level.name if c.class_level else '?'} · {c.subject.name if c.subject else '?'}"
        coverage_by_subject.setdefault(key, {'total': 0, 'completed': 0, 'behind': 0})
        coverage_by_subject[key]['total'] += 1
        if c.status == CoverageStatus.COMPLETED:
            coverage_by_subject[key]['completed'] += 1
        elif c.status == CoverageStatus.BEHIND:
            coverage_by_subject[key]['behind'] += 1

    for key, val in coverage_by_subject.items():
        val['percent'] = round((val['completed'] / val['total']) * 100) if val['total'] else 0

    context = {
        'school': school,
        'teacher': teacher,
        'observations': observations,
        'lesson_plans': lesson_plans,
        'mark_sheets': mark_sheets,
        'coverage_by_subject': coverage_by_subject,
    }
    return render(request, 'dashboards/dpa_acad/teacher_detail.html', context)


# ==========================================================
# TIMETABLE CONFLICTS
# ==========================================================

@dpa_acad_required
def dpa_acad_timetable_conflicts(request):
    """Detect timetable conflicts — teacher double-booked, class double-booked."""
    school = request.user.school

    entries = list(Timetable.objects.filter(school=school).select_related(
        'class_level', 'subject', 'teacher',
    ).order_by('day_of_week', 'start_time'))

    conflicts = []
    seen = []

    for entry in entries:
        for other in seen:
            if entry.day_of_week != other.day_of_week:
                continue

            # Time overlap check: start < other.end AND end > other.start
            overlap = (
                entry.start_time < other.end_time
                and entry.end_time > other.start_time
            )
            if not overlap:
                continue

            # Same teacher conflict
            if entry.teacher and other.teacher and entry.teacher_id == other.teacher_id:
                conflicts.append({
                    'type': 'teacher',
                    'entry_a': entry,
                    'entry_b': other,
                    'reason': f"Teacher {entry.teacher.first_name} {entry.teacher.last_name} assigned to two classes at the same time",
                })

            # Same class conflict
            if entry.class_level_id == other.class_level_id:
                conflicts.append({
                    'type': 'class',
                    'entry_a': entry,
                    'entry_b': other,
                    'reason': f"Class {entry.class_level.name} has two subjects at the same time",
                })

        seen.append(entry)

    # Deduplicate
    unique_conflicts = []
    seen_keys = set()
    for c in conflicts:
        key = tuple(sorted([c['entry_a'].id, c['entry_b'].id])) + (c['type'],)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_conflicts.append(c)

    teacher_conflicts = [c for c in unique_conflicts if c['type'] == 'teacher']
    class_conflicts = [c for c in unique_conflicts if c['type'] == 'class']

    context = {
        'school': school,
        'total_entries': len(entries),
        'conflicts': unique_conflicts,
        'teacher_conflicts': teacher_conflicts,
        'class_conflicts': class_conflicts,
    }
    return render(request, 'dashboards/dpa_acad/timetable_conflicts.html', context)


# ==========================================================
# REMEDIAL CLASSES
# ==========================================================

@dpa_acad_required
def dpa_acad_remedial(request):
    """List of remedial classes."""
    school = request.user.school
    today = timezone.localdate()

    qs = RemedialClass.objects.filter(school=school).select_related(
        'class_level', 'subject', 'teacher',
    ).order_by('-scheduled_date', 'start_time')

    status_filter = request.GET.get('status', '').strip()
    tab = request.GET.get('tab', 'upcoming')

    if status_filter:
        qs = qs.filter(status=status_filter)

    if tab == 'upcoming':
        qs = qs.filter(scheduled_date__gte=today)
    elif tab == 'past':
        qs = qs.filter(scheduled_date__lt=today)

    all_rc = RemedialClass.objects.filter(school=school)

    context = {
        'school': school,
        'today': today,
        'classes': qs[:100],
        'total': qs.count(),
        'tab': tab,
        'status_filter': status_filter,
        'status_choices': RemedialStatus.choices,
        'scheduled_count': all_rc.filter(status=RemedialStatus.SCHEDULED).count(),
        'ongoing_count': all_rc.filter(status=RemedialStatus.ONGOING).count(),
        'completed_count': all_rc.filter(status=RemedialStatus.COMPLETED).count(),
        'cancelled_count': all_rc.filter(status=RemedialStatus.CANCELLED).count(),
    }
    return render(request, 'dashboards/dpa_acad/remedial.html', context)


@dpa_acad_required
def dpa_acad_remedial_create(request):
    """Create a new remedial class."""
    school = request.user.school

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        class_level_id = request.POST.get('class_level')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher') or None
        scheduled_date = request.POST.get('scheduled_date')
        start_time = request.POST.get('start_time') or None
        end_time = request.POST.get('end_time') or None
        location = request.POST.get('location', '').strip()
        focus_area = request.POST.get('focus_area', '').strip()

        if not all([title, class_level_id, subject_id, scheduled_date]):
            messages.error(request, 'Title, class, subject, and date are required.')
        else:
            try:
                rc = RemedialClass.objects.create(
                    school=school,
                    class_level_id=class_level_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    title=title,
                    scheduled_date=scheduled_date,
                    start_time=start_time,
                    end_time=end_time,
                    location=location,
                    focus_area=focus_area,
                    created_by=request.user,
                    status=RemedialStatus.SCHEDULED,
                )
                messages.success(request, 'Remedial class scheduled.')
                return redirect('dpa_acad_remedial')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    context = {
        'school': school,
        'classes': ClassLevel.objects.filter(school=school).order_by('order', 'name'),
        'subjects': Subject.objects.filter(school=school).order_by('name'),
        'teachers': Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name'),
        'today': timezone.localdate(),
    }
    return render(request, 'dashboards/dpa_acad/remedial_form.html', context)


@dpa_acad_required
def dpa_acad_remedial_update(request, class_id):
    """Update remedial class status."""
    if request.method != 'POST':
        return redirect('dpa_acad_remedial')

    rc = get_object_or_404(RemedialClass, pk=class_id, school=request.user.school)
    new_status = request.POST.get('status', rc.status)
    if new_status in [s[0] for s in RemedialStatus.choices]:
        rc.status = new_status
        rc.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Status updated.')
    return redirect('dpa_acad_remedial')
  
  

# ==========================================================
# PDF REPORTS
# ==========================================================

from django.template.loader import render_to_string
from apps.core.pdf_utils import html_to_pdf_response


@dpa_acad_required
def dpa_acad_teacher_pdf(request, teacher_id):
    """PDF summary of one teacher's academic performance."""
    school = request.user.school
    teacher = get_object_or_404(Teacher, pk=teacher_id, school=school)

    observations = TeachingObservation.objects.filter(
        school=school, teacher=teacher,
    ).order_by('-observed_on')[:10]

    # Coverage summary
    coverage = SyllabusCoverage.objects.filter(school=school, teacher=teacher)
    coverage_by_subject = {}
    for c in coverage:
        key = f"{c.class_level.name if c.class_level else '?'} · {c.subject.name if c.subject else '?'}"
        coverage_by_subject.setdefault(key, {'total': 0, 'completed': 0, 'behind': 0})
        coverage_by_subject[key]['total'] += 1
        if c.status == CoverageStatus.COMPLETED:
            coverage_by_subject[key]['completed'] += 1
        elif c.status == CoverageStatus.BEHIND:
            coverage_by_subject[key]['behind'] += 1
    for k, v in coverage_by_subject.items():
        v['percent'] = round((v['completed'] / v['total']) * 100) if v['total'] else 0

    # Lesson plan stats
    plans = LessonPlan.objects.filter(school=school, teacher=teacher)
    plan_stats = {
        'total': plans.count(),
        'approved': plans.filter(status=LessonPlanStatus.APPROVED).count(),
        'submitted': plans.filter(status=LessonPlanStatus.SUBMITTED).count(),
        'revision': plans.filter(status=LessonPlanStatus.REVISION).count(),
    }

    # Mark sheet stats
    sheets = MarkSheet.objects.filter(school=school, teacher=teacher)
    sheet_stats = {
        'total': sheets.count(),
        'published': sheets.filter(status=MarkSheetStatus.PUBLISHED).count(),
        'approved': sheets.filter(status=MarkSheetStatus.APPROVED).count(),
        'submitted': sheets.filter(status=MarkSheetStatus.SUBMITTED).count(),
    }

    html_string = render_to_string('pdf/dpa_acad_teacher.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            teacher=teacher,
            observations=observations,
            coverage_by_subject=coverage_by_subject,
            plan_stats=plan_stats,
            sheet_stats=sheet_stats,
        )
    )

    filename = f"teacher_performance_{teacher.id}.pdf"
    return html_to_pdf_response(html_string, filename)



# ==========================================================
# STREAM-SUBJECT ASSIGNMENT GRID
# ==========================================================

@dpa_acad_required
def dpa_acad_stream_subjects(request):
    """
    Grid view: streams × subjects, showing currently-assigned teacher.
    Click a cell to reassign.
    """
    school = request.user.school
    today = timezone.localdate()

    year_str = request.GET.get('year', str(today.year)).strip()
    try:
        year = int(year_str)
    except ValueError:
        year = today.year

    term = request.GET.get('term', '').strip()

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    subjects = Subject.objects.filter(school=school).order_by('name')
    teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')

    # Fetch existing assignments
    qs = StreamSubjectTeacher.objects.filter(
        school=school, academic_year=year,
    ).select_related('class_level', 'subject', 'teacher')
    if term:
        qs = qs.filter(term=term)

    # Build lookup map
    assignment_map = {}
    for a in qs:
        assignment_map[(a.class_level_id, a.subject_id)] = a

    # Build grid rows
    rows = []
    for cls in classes:
        cells = []
        for subj in subjects:
            a = assignment_map.get((cls.id, subj.id))
            cells.append({
                'subject': subj,
                'assignment': a,
                'teacher': a.teacher if a else None,
                'assignment_id': a.id if a else None,
            })
        rows.append({'class_level': cls, 'cells': cells})

    # Stats
    total_cells = classes.count() * subjects.count()
    assigned = qs.count()
    unassigned = max(0, total_cells - assigned)

    # Years in use
    years = list(
        StreamSubjectTeacher.objects.filter(school=school)
        .values_list('academic_year', flat=True)
        .distinct()
        .order_by('-academic_year')
    )
    if year not in years:
        years.insert(0, year)

    context = {
        'school': school,
        'rows': rows,
        'subjects': subjects,
        'teachers': teachers,
        'year': year,
        'term': term,
        'years': years,
        'total_cells': total_cells,
        'assigned': assigned,
        'unassigned': unassigned,
    }
    return render(request, 'dashboards/dpa_acad/stream_subjects.html', context)


@dpa_acad_required
def dpa_acad_stream_subject_assign(request):
    """
    Assign a teacher to a (class, subject, year, term).
    Called via AJAX POST from the grid.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    if request.user.role not in (Role.DEPUTY_ACADEMICS, Role.PRINCIPAL):
        return JsonResponse({'ok': False, 'error': 'Not permitted'}, status=403)

    class_level_id = request.POST.get('class_level')
    subject_id = request.POST.get('subject')
    teacher_id = request.POST.get('teacher') or None
    academic_year = request.POST.get('year')
    term = request.POST.get('term', '').strip()

    if not class_level_id or not subject_id or not academic_year:
        return JsonResponse({'ok': False, 'error': 'Missing fields'}, status=400)

    try:
        academic_year = int(academic_year)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Invalid year'}, status=400)

    try:
        cls = ClassLevel.objects.get(pk=class_level_id, school=request.user.school)
        subj = Subject.objects.get(pk=subject_id, school=request.user.school)
    except (ClassLevel.DoesNotExist, Subject.DoesNotExist):
        return JsonResponse({'ok': False, 'error': 'Invalid class/subject'}, status=404)

    teacher = None
    if teacher_id:
        try:
            teacher = Teacher.objects.get(pk=teacher_id, school=request.user.school)
        except Teacher.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Teacher not found'}, status=404)

    obj, created = StreamSubjectTeacher.objects.update_or_create(
        school=request.user.school,
        class_level=cls,
        subject=subj,
        academic_year=academic_year,
        term=term,
        defaults={
            'teacher': teacher,
            'assigned_by': request.user,
        },
    )

    # Also keep Timetable in sync for any existing periods
    Timetable.objects.filter(
        school=request.user.school,
        class_level=cls,
        subject=subj,
    ).update(teacher=teacher)

    return JsonResponse({
        'ok': True,
        'created': created,
        'teacher': (
            f"{teacher.first_name} {teacher.last_name}"
            if teacher else None
        ),
        'teacher_id': teacher.id if teacher else None,
        'assignment_id': obj.id,
    })
    
    

# ==========================================================
# TIMETABLE — stream view + teacher view
# ==========================================================

# Ordered day names for grid display
DAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
DAY_LABELS = {
    'monday': 'Monday',
    'tuesday': 'Tuesday',
    'wednesday': 'Wednesday',
    'thursday': 'Thursday',
    'friday': 'Friday',
    'saturday': 'Saturday',
}


def _build_stream_grid(school, class_level):
    """
    Build a matrix of timetable entries for one stream.
    Uses the canonical SCHOOL_DAY structure — breaks included.
    """
    entries = Timetable.objects.filter(
        school=school, class_level=class_level,
    ).select_related('subject', 'teacher')

    slots = _build_period_slots()

    # Lookup: (day, slot_key) -> entry
    lookup = {}
    for e in entries:
        day = e.day_of_week
        slot_key = f"{e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')}"
        lookup[(day, slot_key)] = e

    days = [{'key': d, 'label': DAY_LABELS[d]} for d in DAY_ORDER]

    # Build matrix — rows = days, cells = slots (lessons + breaks)
    matrix = []
    for day in days:
        row_cells = []
        for slot in slots:
            if slot['kind'] == 'break':
                row_cells.append({
                    'is_break': True,
                    'label': slot['label'],
                })
            else:
                entry = lookup.get((day['key'], slot['key']))
                row_cells.append({
                    'is_break': False,
                    'slot': slot,
                    'entry': entry,
                })
        matrix.append({'day': day, 'cells': row_cells})

    return {
        'days': days,
        'periods': slots,           # full day slots, breaks included
        'matrix': matrix,
    }


@dpa_acad_required
def dpa_acad_timetable_stream(request, class_id):
    """On-screen timetable grid for one stream."""
    school = request.user.school
    class_level = get_object_or_404(ClassLevel, pk=class_id, school=school)

    grid_data = _build_stream_grid(school, class_level)

    context = {
        'school': school,
        'class_level': class_level,
        'days': grid_data['days'],
        'periods': grid_data['periods'],
        'matrix': grid_data['matrix'],
        'total_entries': Timetable.objects.filter(
            school=school, class_level=class_level,
        ).count(),
    }
    return render(request, 'dashboards/dpa_acad/timetable_stream.html', context)


@dpa_acad_required
def dpa_acad_timetable_stream_pdf(request, class_id):
    """PDF timetable for one stream."""
    school = request.user.school
    class_level = get_object_or_404(ClassLevel, pk=class_id, school=school)

    grid_data = _build_stream_grid(school, class_level)


    html_string = render_to_string('pdf/dpa_acad_timetable_stream.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            class_level=class_level,
            days=grid_data['days'],
            periods=grid_data['periods'],
            matrix=grid_data['matrix'],
        )
    )

    filename = f"timetable_{class_level.name.replace(' ', '_')}.pdf"
    return html_to_pdf_response(html_string, filename)


@dpa_acad_required
def dpa_acad_timetable_list(request):
    """List all streams with their timetable status."""
    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    rows = []
    for cls in classes:
        count = Timetable.objects.filter(school=school, class_level=cls).count()
        rows.append({
            'class_level': cls,
            'entries': count,
            'has_timetable': count > 0,
        })

    context = {
        'school': school,
        'rows': rows,
        'total_streams': len(rows),
        'streams_with_timetable': sum(1 for r in rows if r['has_timetable']),
    }
    return render(request, 'dashboards/dpa_acad/timetable_list.html', context)


# ==========================================================
# TEACHER PERSONAL TIMETABLE
# ==========================================================

def _build_teacher_grid(school, teacher):
    """Build a matrix of a teacher's timetable — all classes. Breaks included."""
    entries = Timetable.objects.filter(
        school=school, teacher=teacher.user,
    ).select_related('class_level', 'subject')
    slots = _build_period_slots()

    lookup = {}
    for e in entries:
        day = e.day_of_week
        slot_key = f"{e.start_time.strftime('%H:%M')}-{e.end_time.strftime('%H:%M')}"
        lookup[(day, slot_key)] = e

    days = [{'key': d, 'label': DAY_LABELS[d]} for d in DAY_ORDER]

    matrix = []
    for day in days:
        row_cells = []
        for slot in slots:
            if slot['kind'] == 'break':
                row_cells.append({
                    'is_break': True,
                    'label': slot['label'],
                })
            else:
                entry = lookup.get((day['key'], slot['key']))
                row_cells.append({
                    'is_break': False,
                    'slot': slot,
                    'entry': entry,
                })
        matrix.append({'day': day, 'cells': row_cells})

    return {
        'days': days,
        'periods': slots,
        'matrix': matrix,
        'total': entries.count(),
    }
    
    # ==========================================================
# STANDARD KENYAN SECONDARY SCHOOL DAY (CBC JSS)
# Matches the reference timetable layout
# ==========================================================

SCHOOL_DAY = [
    ('8:00', '8:40', 'lesson'),         # Period 1
    ('8:40', '9:20', 'lesson'),         # Period 2
    ('9:20', '9:30', 'break'),          # Short Break (10 min)
    ('9:30', '10:10', 'lesson'),        # Period 3
    ('10:10', '10:50', 'lesson'),       # Period 4
    ('10:50', '11:20', 'break'),        # Long Break (30 min)
    ('11:20', '12:00', 'lesson'),       # Period 5
    ('12:00', '12:40', 'lesson'),       # Period 6
    ('12:40', '14:00', 'break'),        # Lunch (1hr 20min)
    ('14:00', '14:40', 'lesson'),       # Period 7
    ('14:40', '15:20', 'lesson'),       # Period 8
    ('15:20', '16:00', 'lesson'),       # Period 9
]

BREAK_LABELS = {
    '9:20-9:30': 'SHORT BREAK',
    '10:50-11:20': 'LONG BREAK',
    '12:40-14:00': 'LUNCH BREAK',
}


def _build_period_slots():
    """
    Return list of period dicts from SCHOOL_DAY.
    Each dict: {'label', 'start', 'end', 'key', 'kind', 'start_display', 'end_display', 'time_display'}
    """
    from datetime import datetime as _dt

    slots = []
    lesson_num = 0
    for start_s, end_s, kind in SCHOOL_DAY:
        start_t = _dt.strptime(start_s, '%H:%M').time()
        end_t = _dt.strptime(end_s, '%H:%M').time()
        key = f"{start_s}-{end_s}"

        if kind == 'break':
            label = BREAK_LABELS.get(key, 'BREAK')
        else:
            lesson_num += 1
            label = f"Period {lesson_num}"

        slots.append({
            'label': label,
            'start': start_t,
            'end': end_t,
            'key': key,
            'kind': kind,
            'start_display': start_s,
            'end_display': end_s,
            'time_display': f"{start_s} - {end_s}",
        })
    return slots
@login_required
def teacher_my_timetable(request):
    """Teacher's personal timetable — reachable from their dashboard."""
    # Allow teachers, class teachers, or admins previewing
    user = request.user
    if user.role not in (Role.TEACHER, Role.CLASS_TEACHER, Role.PRINCIPAL,
                        Role.DEPUTY_ADMIN, Role.DEPUTY_ACADEMICS,
                        Role.DIRECTOR_OF_STUDIES, Role.SUPER_ADMIN):
        return HttpResponseForbidden("You do not have access to this page.")

    school = user.school
    if school is None:
        return HttpResponseForbidden("Your account is not linked to a school.")

    # Find the teacher profile
    teacher = Teacher.objects.filter(school=school, user=user).first()
    if teacher is None:
        # Admin viewing without teacher profile — show picker
        teachers = Teacher.objects.filter(school=school, is_active=True).order_by('first_name')
        return render(request, 'dashboards/dpa_acad/teacher_timetable_picker.html', {
            'school': school,
            'teachers': teachers,
        })

    grid_data = _build_teacher_grid(school, teacher)
    today_key = timezone.localdate().strftime('%A').lower()
    todays_periods = _teacher_today_periods(school, teacher, today_key)

    context = {
        'school': school,
        'teacher': teacher,
        'days': grid_data['days'],
        'periods': grid_data['periods'],
        'matrix': grid_data['matrix'],   # was 'grid'
        'total': grid_data['total'],
        'today_label': timezone.localdate().strftime('%A'),
        'todays_periods': todays_periods,
    }
    return render(request, 'dashboards/dpa_acad/teacher_timetable.html', context)


@login_required
def teacher_my_timetable_pdf(request):
    """Teacher's personal timetable as PDF."""
    user = request.user
    school = user.school
    if school is None:
        return HttpResponseForbidden("Your account is not linked to a school.")

    teacher = Teacher.objects.filter(school=school, user=user).first()
    if teacher is None:
        return HttpResponseForbidden("No teacher profile found.")

    grid_data = _build_teacher_grid(school, teacher)

    html_string = render_to_string('pdf/dpa_acad_teacher_timetable.html',
        build_pdf_context(
            school=school,
            generated_by=user,
            teacher=teacher,
            days=grid_data['days'],
            periods=grid_data['periods'],
            matrix=grid_data['matrix'],
        )
    )
    filename = f"timetable_{teacher.first_name}_{teacher.last_name}.pdf"
    return html_to_pdf_response(html_string, filename)


@dpa_acad_required
def dpa_acad_teacher_timetable_pdf(request, teacher_id):
    """Admin version — view any teacher's timetable as PDF."""
    school = request.user.school
    teacher = get_object_or_404(Teacher, pk=teacher_id, school=school)

    grid_data = _build_teacher_grid(school, teacher)

    html_string = render_to_string('pdf/dpa_acad_teacher_timetable.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            teacher=teacher,
            days=grid_data['days'],
            periods=grid_data['periods'],
            matrix=grid_data['matrix'],
        )
    )
    filename = f"timetable_{teacher.first_name}_{teacher.last_name}.pdf"
    return html_to_pdf_response(html_string, filename)


def _teacher_today_periods(school, teacher, today_key=None):
    """Return today's periods for a teacher, sorted by time."""
    if today_key is None:
        today_key = timezone.localdate().strftime('%A').lower()
        if today_key not in DAY_ORDER:
            today_key = 'monday'

    return list(
        Timetable.objects.filter(
            school=school, teacher=teacher.user, day_of_week=today_key,
        ).select_related('class_level', 'subject').order_by('start_time')
    )
    
@dpa_acad_required
def _test_header_pdf(request):
    """TEMPORARY test view — remove after verifying header."""
    from django.template.loader import render_to_string
    from apps.core.pdf_utils import build_pdf_context, html_to_pdf_response

    html_string = render_to_string('pdf/_test_header.html',
        build_pdf_context(
            school=request.user.school,
            generated_by=request.user,
        )
    )
    return html_to_pdf_response(html_string, 'test_header.pdf')