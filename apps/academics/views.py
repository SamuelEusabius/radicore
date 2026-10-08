from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from rest_framework import viewsets

from .models import ClassLevel, Subject, Timetable
from .serializers import ClassLevelSerializer, SubjectSerializer, TimetableSerializer
from .forms import TimetableForm
from apps.accounts.permissions import IsSchoolAdmin


# ---------------- API ViewSets (existing) ----------------
class SchoolScopedMixin:
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_super_admin:
            return qs
        return qs.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)


class ClassLevelViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer
    permission_classes = [IsSchoolAdmin]


class SubjectViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.select_related('teacher')
    serializer_class = SubjectSerializer
    permission_classes = [IsSchoolAdmin]


class TimetableViewSet(SchoolScopedMixin, viewsets.ModelViewSet):
    queryset = Timetable.objects.select_related('class_level', 'subject', 'teacher')
    serializer_class = TimetableSerializer
    permission_classes = [IsSchoolAdmin]


# ---------------- HTML Views (new) ----------------

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


@login_required
def timetable_grid(request):
    """
    Weekly grid view for the timetable.
    Shows a 5-day grid with subjects in columns.
    """
    school = request.user.school
    if not school:
        messages.error(request, 'You are not attached to a school.')
        return redirect('dashboard_home')

    # Filter by class
    selected_class_id = request.GET.get('class')
    classes = ClassLevel.objects.filter(school=school)

    selected_class = None
    if selected_class_id:
        selected_class = classes.filter(id=selected_class_id).first()
    elif classes.exists():
        selected_class = classes.first()

    # Build grid
    entries = []
    time_slots = []

    if selected_class:
        entries = Timetable.objects.filter(
            school=school, class_level=selected_class
        ).select_related('subject', 'teacher')

        # Unique time slots from entries
        slot_set = set()
        for e in entries:
            slot_set.add((e.start_time, e.end_time))
        time_slots = sorted(slot_set)

    # Build a lookup: (time_slot, day) -> entry
    grid = {}
    for e in entries:
        grid[(e.start_time, e.end_time, e.day_of_week)] = e

    # Build rows: for each time slot, list entries for each day
    rows = []
    for slot in time_slots:
        row = {'slot': slot, 'days': {}}
        for day in DAYS:
            row['days'][day] = grid.get((slot[0], slot[1], day))
        rows.append(row)

    return render(request, 'dashboard/timetable_grid.html', {
        'classes': classes,
        'selected_class': selected_class,
        'days': DAYS,
        'rows': rows,
    })


@login_required
def timetable_manage(request):
    """
    Manage timetable entries — create/edit/delete.
    Only school admins can access.
    """
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    entries = Timetable.objects.filter(school=school).select_related(
        'class_level', 'subject', 'teacher'
    ).order_by('day_of_week', 'start_time')

    return render(request, 'dashboard/timetable_manage.html', {
        'entries': entries,
    })


@login_required
def timetable_add(request):
    """Add a new timetable entry."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        form.fields['class_level'].queryset = ClassLevel.objects.filter(school=school)
        form.fields['subject'].queryset = Subject.objects.filter(school=school)
        form.fields['teacher'].queryset = form.fields['teacher'].queryset.filter(school=school)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.school = school
            entry.save()
            messages.success(request, f'Added {entry.subject} for {entry.class_level} on {entry.day_of_week}.')
            return redirect('timetable_manage')
    else:
        form = TimetableForm()
        form.fields['class_level'].queryset = ClassLevel.objects.filter(school=school)
        form.fields['subject'].queryset = Subject.objects.filter(school=school)
        form.fields['teacher'].queryset = form.fields['teacher'].queryset.filter(school=school)

    return render(request, 'dashboard/timetable_form.html', {
        'form': form,
        'action': 'Add',
    })


@login_required
def timetable_edit(request, entry_id):
    """Edit a timetable entry."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    entry = get_object_or_404(Timetable, id=entry_id, school=school)

    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=entry)
        form.fields['class_level'].queryset = ClassLevel.objects.filter(school=school)
        form.fields['subject'].queryset = Subject.objects.filter(school=school)
        form.fields['teacher'].queryset = form.fields['teacher'].queryset.filter(school=school)

        if form.is_valid():
            form.save()
            messages.success(request, 'Timetable entry updated.')
            return redirect('timetable_manage')
    else:
        form = TimetableForm(instance=entry)
        form.fields['class_level'].queryset = ClassLevel.objects.filter(school=school)
        form.fields['subject'].queryset = Subject.objects.filter(school=school)
        form.fields['teacher'].queryset = form.fields['teacher'].queryset.filter(school=school)

    return render(request, 'dashboard/timetable_form.html', {
        'form': form,
        'action': 'Edit',
        'entry': entry,
    })


@login_required
def timetable_delete(request, entry_id):
    """Delete a timetable entry."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    entry = get_object_or_404(Timetable, id=entry_id, school=request.user.school)
    entry.delete()
    messages.success(request, 'Timetable entry deleted.')
    return redirect('timetable_manage')