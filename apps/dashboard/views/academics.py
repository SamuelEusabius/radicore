"""
Academics views:
- Class management (create, edit, delete)
- Subject management (create, edit, delete)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum

from apps.accounts.decorators import (
    role_required, school_staff_only,
)


@login_required
def manage_classes(request):
    """Manage school classes — list, add, edit, delete."""
    if request.user.role != 'principal':
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from django.db.models import Count, Q, Prefetch

    school = request.user.school

    # ---------- POST: Add ----------
    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'add':
            name = (request.POST.get('name') or '').strip().upper()
            order = request.POST.get('order', 0)
            try:
                order = int(order)
            except (ValueError, TypeError):
                order = 0

            if not name:
                messages.error(request, 'Class name is required.')
            elif ClassLevel.objects.filter(school=school, name=name).exists():
                messages.error(request, f'Class "{name}" already exists.')
            else:
                ClassLevel.objects.create(school=school, name=name, order=order)
                messages.success(request, f'Class "{name}" added.')
            return redirect('manage_classes')

        elif action == 'edit':
            class_id = request.POST.get('class_id')
            name = (request.POST.get('name') or '').strip().upper()
            order = request.POST.get('order', 0)
            try:
                order = int(order)
            except (ValueError, TypeError):
                order = 0

            cls = ClassLevel.objects.filter(id=class_id, school=school).first()
            if not cls:
                messages.error(request, 'Class not found.')
            elif not name:
                messages.error(request, 'Class name is required.')
            elif ClassLevel.objects.filter(school=school, name=name).exclude(id=cls.id).exists():
                messages.error(request, f'Another class named "{name}" already exists.')
            else:
                old_name = cls.name
                cls.name = name
                cls.order = order
                cls.save()
                # Update students' class_level string to match
                if old_name != name:
                    Student.objects.filter(
                        school=school, class_level=old_name
                    ).update(class_level=name)
                messages.success(request, f'Class updated to "{name}".')
            return redirect('manage_classes')

        elif action == 'delete':
            class_id = request.POST.get('class_id')
            cls = ClassLevel.objects.filter(id=class_id, school=school).first()
            if not cls:
                messages.error(request, 'Class not found.')
            else:
                # Check for students
                student_count = Student.objects.filter(
                    school=school, class_level=cls.name, is_active=True
                ).count()
                if student_count > 0:
                    messages.error(
                        request,
                        f'Cannot delete "{cls.name}" — {student_count} student{"s" if student_count != 1 else ""} still assigned. Reassign them first.'
                    )
                else:
                    name = cls.name
                    cls.delete()
                    messages.success(request, f'Class "{name}" deleted.')
            return redirect('manage_classes')

    # ---------- GET: List ----------
    search = request.GET.get('q', '').strip()

    classes_qs = ClassLevel.objects.filter(school=school)

    if search:
        classes_qs = classes_qs.filter(name__icontains=search)

    classes_qs = classes_qs.order_by('order', 'name')

    # Count students per class by matching name (string field)
    classes_with_counts = []
    total_students = 0

    for cls in classes_qs:
        s_count = Student.objects.filter(
            school=school, class_level=cls.name, is_active=True
        ).count()
        total_students += s_count

        # Class teacher?
        class_teacher = Teacher.objects.filter(
            school=school, current_class=cls, is_class_teacher=True, is_active=True
        ).select_related('user').first()

        classes_with_counts.append({
            'class': cls,
            'student_count': s_count,
            'class_teacher': class_teacher,
        })

    # Stats
    total_classes = ClassLevel.objects.filter(school=school).count()
    active_students = Student.objects.filter(school=school, is_active=True).count()

    return render(request, 'dashboard/manage_classes.html', {
        'classes_with_counts': classes_with_counts,
        'search': search,
        'stats': {
            'total_classes': total_classes,
            'total_students': active_students,
            'levels': len(set(
                c.name.split()[1] if len(c.name.split()) > 1 else c.name
                for c in ClassLevel.objects.filter(school=school)
            )),
        },
    })


@login_required
def manage_subjects(request):
    """Manage subjects — list, add, edit, delete."""
    if request.user.role != 'principal':
        return redirect('dashboard_home')

    from apps.academics.models import Subject
    from apps.accounts.models import User
    from django.db.models import Q, Count
    from django.core.paginator import Paginator
    # Try to import User properly
    try:
        from apps.accounts.models import User
    except ImportError:
        from django.contrib.auth import get_user_model
        User = get_user_model()

    school = request.user.school

    # ==========================================================
    # POST — add / edit / delete
    # ==========================================================
    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'add':
            name = (request.POST.get('name') or '').strip()
            code = (request.POST.get('code') or '').strip()
            teacher_id = request.POST.get('teacher') or None

            if not name:
                messages.error(request, 'Subject name is required.')
            elif Subject.objects.filter(school=school, name=name).exists():
                messages.error(request, f'Subject "{name}" already exists.')
            else:
                Subject.objects.create(
                    school=school,
                    name=name,
                    code=code,
                    teacher_id=teacher_id,
                )
                messages.success(request, f'Subject "{name}" added.')
            return redirect('manage_subjects')

        elif action == 'edit':
            subject_id = request.POST.get('subject_id')
            subject = Subject.objects.filter(id=subject_id, school=school).first()
            if not subject:
                messages.error(request, 'Subject not found.')
                return redirect('manage_subjects')

            name = (request.POST.get('name') or '').strip()
            code = (request.POST.get('code') or '').strip()
            teacher_id = request.POST.get('teacher') or None

            if not name:
                messages.error(request, 'Subject name is required.')
            elif Subject.objects.filter(school=school, name=name).exclude(id=subject.id).exists():
                messages.error(request, f'Another subject named "{name}" already exists.')
            else:
                subject.name = name
                subject.code = code
                subject.teacher_id = teacher_id
                subject.save()
                messages.success(request, f'Subject "{name}" updated.')
            return redirect('manage_subjects')

        elif action == 'delete':
            subject_id = request.POST.get('subject_id')
            subject = Subject.objects.filter(id=subject_id, school=school).first()
            if not subject:
                messages.error(request, 'Subject not found.')
            else:
                name = subject.name
                subject.delete()
                messages.success(request, f'Subject "{name}" deleted.')
            return redirect('manage_subjects')

    # ==========================================================
    # GET — list
    # ==========================================================
    search = request.GET.get('q', '').strip()
    teacher_filter = request.GET.get('teacher', '').strip()
    status_filter = request.GET.get('status', '').strip()

    base_qs = Subject.objects.filter(school=school).select_related('teacher')
    qs = base_qs.order_by('name')

    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(code__icontains=search)
        )

    if teacher_filter:
        if teacher_filter == 'none':
            qs = qs.filter(teacher__isnull=True)
        else:
            qs = qs.filter(teacher_id=teacher_filter)

    if status_filter == 'assigned':
        qs = qs.filter(teacher__isnull=False)
    elif status_filter == 'unassigned':
        qs = qs.filter(teacher__isnull=True)

    # ---------- Stats ----------
    stats = {
        'total': base_qs.count(),
        'assigned': base_qs.filter(teacher__isnull=False).count(),
        'unassigned': base_qs.filter(teacher__isnull=True).count(),
        'teachers': base_qs.filter(teacher__isnull=False).values('teacher').distinct().count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ---------- Teachers for dropdown ----------
    teachers = User.objects.filter(
        school=school, role='teacher'
    ).order_by('first_name', 'last_name')

    return render(request, 'dashboard/manage_subjects.html', {
        'subjects': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'teacher_filter': teacher_filter,
        'status_filter': status_filter,
        'teachers': teachers,
        'total_filtered': qs.count(),
    })


@login_required
def subject_delete(request, subject_id):
    """Confirm and delete a subject."""
    if request.user.role != 'principal':
        return redirect('dashboard_home')

    from apps.academics.models import Subject

    subject = get_object_or_404(Subject, id=subject_id, school=request.user.school)

    if request.method == 'POST':
        name = subject.name
        subject.delete()
        messages.success(request, f'Subject "{name}" deleted.')
        return redirect('manage_subjects')

    return render(request, 'dashboard/subject_delete_confirm.html', {
        'subject': subject,
    })


