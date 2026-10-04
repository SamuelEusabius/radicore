"""
Timetable views:
- Weekly timetable grid
- Add/delete timetable entries
- Timetable PDF export
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
)


# School timetable periods — includes breaks as visual rows
TIMETABLE_PERIODS = [
    # ('start', 'end', 'type', 'label')
    ('08:00', '08:40', 'lesson', 'Period 1'),
    ('08:40', '09:20', 'lesson', 'Period 2'),
    ('09:20', '09:35', 'short_break', 'Short Break'),
    ('09:35', '10:15', 'lesson', 'Period 3'),
    ('10:15', '10:55', 'lesson', 'Period 4'),
    ('10:55', '11:20', 'long_break', 'Long Break'),
    ('11:20', '12:00', 'lesson', 'Period 5'),
    ('12:00', '12:40', 'lesson', 'Period 6'),
    ('12:40', '14:00', 'lunch', 'Lunch Break'),
    ('14:00', '14:40', 'lesson', 'Period 7'),
    ('14:40', '15:20', 'lesson', 'Period 8'),
    ('15:20', '16:30', 'games', 'Games Time'),
]

# Only the "lesson" periods — used by the grid to place entries
DEFAULT_PERIODS = [(p[0], p[1]) for p in TIMETABLE_PERIODS if p[2] == 'lesson']


@login_required
def timetable_view(request):
    """Show the weekly timetable grid for a class."""
    from apps.academics.models import ClassLevel, Subject, Timetable
    from apps.teachers.models import Teacher

    user = request.user
    school = user.school

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    class_id = request.GET.get('class')

    if not class_id and classes.exists():
        class_id = classes.first().id

    selected_class = None
    grid = {}
    class_teacher = None

    if class_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
        except ClassLevel.DoesNotExist:
            pass

    if selected_class:
        entries = Timetable.objects.filter(
            school=school, class_level=selected_class
        ).select_related('subject', 'teacher')

        class_teacher = Teacher.objects.filter(
            school=school, current_class=selected_class, is_class_teacher=True
        ).select_related('user').first()

        # grid = { 'MON': { '08:00': entry, ... }, ... }
        for entry in entries:
            day = entry.day_of_week
            start = entry.start_time.strftime('%H:%M')
            grid.setdefault(day, {})[start] = entry

    palette = ['#0d9488', '#7c3aed', '#2563eb', '#ea580c', '#be123c',
               '#059669', '#db2777', '#0891b2', '#65a30d', '#d97706']
    subjects = Subject.objects.filter(school=school).order_by('name')
    subject_colors = {s.id: palette[i % len(palette)] for i, s in enumerate(subjects)}

    return render(request, 'dashboard/timetable_grid.html', {
        'classes': classes,
        'selected_class': selected_class,
        'periods': TIMETABLE_PERIODS,
        'days': [
            ('MON', 'Monday'),
            ('TUE', 'Tuesday'),
            ('WED', 'Wednesday'),
            ('THU', 'Thursday'),
            ('FRI', 'Friday'),
            ('SAT', 'Saturday'),
        ],
        'grid': grid,
        'subjects': subjects,
        'subject_colors': subject_colors,
        'class_teacher': class_teacher,
    })


@login_required
def timetable_add(request):
    """Add a timetable entry."""
    if request.user.role != 'school_admin':
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel, Subject, Timetable

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school)
    subjects = Subject.objects.filter(school=school)
    teachers = User.objects.filter(school=school, role='teacher')

    if request.method == 'POST':
        class_id = request.POST.get('class_level')
        day = request.POST.get('day_of_week')
        subject_id = request.POST.get('subject')
        teacher_id = request.POST.get('teacher') or None
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')

        if not (class_id and day and subject_id and start and end):
            messages.error(request, 'Please fill all required fields.')
        else:
            conflict = Timetable.objects.filter(
                school=school, class_level_id=class_id,
                day_of_week=day, start_time=start,
            ).exists()

            if conflict:
                messages.error(request, f'This class already has a lesson at {start} on {day}.')
            else:
                Timetable.objects.create(
                    school=school,
                    class_level_id=class_id,
                    subject_id=subject_id,
                    teacher_id=teacher_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                )
                messages.success(request, 'Lesson added to timetable.')
                return redirect(f'/dashboard/timetable/?class={class_id}')

    lesson_periods = [(p[0], p[1]) for p in TIMETABLE_PERIODS if p[2] == 'lesson']
    return render(request, 'dashboard/timetable_form.html', {
        'classes': classes,
        'subjects': subjects,
        'teachers': teachers,
        'days': Timetable.Day.choices,
        'periods': lesson_periods,
    })


@login_required
def timetable_delete(request, entry_id):
    """Delete a timetable entry."""
    if request.user.role != 'school_admin':
        return redirect('dashboard_home')

    from apps.academics.models import Timetable

    entry = get_object_or_404(Timetable, id=entry_id, school=request.user.school)
    class_id = entry.class_level_id
    entry.delete()
    messages.success(request, 'Lesson removed.')
    return redirect(f'/dashboard/timetable/?class={class_id}')


@login_required
def timetable_pdf(request):
    """Generate a timetable PDF (A4 landscape)."""
    if request.user.role not in ('teacher', 'school_admin', 'accountant'):
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel, Subject, Timetable
    from apps.teachers.models import Teacher
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    school = user.school

    class_id = request.GET.get('class')
    selected_class = None
    grid = {}
    class_teacher = None

    if class_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
        except ClassLevel.DoesNotExist:
            messages.error(request, 'Invalid class.')
            return redirect('timetable_view')
    else:
        # Default to first class
        first_class = ClassLevel.objects.filter(school=school).first()
        if first_class:
            selected_class = first_class

    if selected_class:
        entries = Timetable.objects.filter(
            school=school, class_level=selected_class
        ).select_related('subject', 'teacher')

        class_teacher = Teacher.objects.filter(
            school=school, current_class=selected_class, is_class_teacher=True
        ).select_related('user').first()

        for entry in entries:
            day = entry.day_of_week
            start = entry.start_time.strftime('%H:%M')
            grid.setdefault(day, {})[start] = entry

    html_string = render_to_string('pdf/timetable.html', {
        'school': school,
        'selected_class': selected_class,
        'periods': TIMETABLE_PERIODS,
        'days': [
            ('MON', 'Monday'),
            ('TUE', 'Tuesday'),
            ('WED', 'Wednesday'),
            ('THU', 'Thursday'),
            ('FRI', 'Friday'),
            ('SAT', 'Saturday'),
        ],
        'grid': grid,
        'class_teacher': class_teacher,
    })

    filename = f'timetable_{selected_class.name if selected_class else "class"}.pdf'
    return html_to_pdf_response(html_string, filename)


