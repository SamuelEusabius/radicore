from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F, Q
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
import json
from apps.accounts.decorators import (
    role_required, super_admin_only, school_staff_only,
    teacher_only, parent_only, accountant_only, student_only,
    class_teacher_only,
)

User = get_user_model()


# ==========================================================
# DASHBOARD ROUTER
# ==========================================================

def redirect_to_own_dashboard(request):
    """Send the user to their OWN dashboard based on their role."""
    role = request.user.role

    redirect_map = {
        'super_admin': 'dash_super_admin',
        'school_admin': 'dash_school_admin',
        'teacher': 'dash_teacher',
        'parent': 'dash_parent',
        'accountant': 'dash_accountant',
        'student': 'dash_student',
    }

    target = redirect_map.get(role)
    if target:
        return redirect(target)

    return redirect('landing')

# ==========================================================
# SUPER ADMIN
# ==========================================================

# ==========================================================
# SCHOOL ADMIN
# ==========================================================

@login_required
@school_staff_only
def school_admin_dash(request):
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.parents.models import Parent
    from apps.staff.models import NonTeachingStaff
    from apps.academics.models import ClassLevel, Subject
    from apps.finance.models import Invoice

    school = request.user.school

    students_qs = Student.objects.filter(school=school, is_active=True)
    teachers_qs = Teacher.objects.filter(school=school, is_active=True).select_related('user', 'current_class')
    parents_qs = Parent.objects.filter(user__school=school).select_related('user').prefetch_related('students')
    staff_qs = NonTeachingStaff.objects.filter(school=school, is_active=True).order_by('role', 'full_name')

    invoices = Invoice.objects.filter(student__school=school)
    total_outstanding = sum(i.balance for i in invoices)

    return render(request, 'dashboard/school_admin.html', {
        'student_count': students_qs.count(),
        'teacher_count': teachers_qs.count(),
        'parent_count': parents_qs.count(),
        'staff_count': staff_qs.count(),
        'class_count': ClassLevel.objects.filter(school=school).count(),
        'subject_count': Subject.objects.filter(school=school).count(),
        'total_outstanding': total_outstanding,
        'recent_students': students_qs.order_by('-created_at')[:5],
        'recent_teachers': teachers_qs[:5],
        'recent_parents': parents_qs[:5],
        'recent_staff': staff_qs[:5],
    })


# ==========================================================
# PEOPLE LISTS
# ==========================================================


@login_required
def staff_list(request):
    """List non-teaching staff with filters and stats."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    school = request.user.school
    base_qs = NonTeachingStaff.objects.filter(school=school)

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs.order_by('role', 'full_name')

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(id_number__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )

    if role_filter:
        qs = qs.filter(role=role_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # ---------- Stats ----------
    stats = {
        'total': base_qs.count(),
        'active': base_qs.filter(is_active=True).count(),
        'security': base_qs.filter(role='security').count(),
        'cooks': base_qs.filter(role='cook').count(),
        'drivers': base_qs.filter(role='driver').count(),
        'cleaners': base_qs.filter(role='cleaner').count(),
    }

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/staff_list.html', {
        'staff': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'roles': NonTeachingStaff.Role.choices,
        'total_filtered': qs.count(),
    })

# ==========================================================
# USER MANAGEMENT
# ==========================================================


@login_required
def user_deactivate(request, user_id):
    """Toggle user is_active (deactivate or reactivate)."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.accounts.models import User
    from django.views.decorators.http import require_POST

    if request.method != 'POST':
        return redirect('manage_users')

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    # Cannot deactivate yourself
    if target.id == request.user.id:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('manage_users')

    # Cannot deactivate a super_admin unless you are one
    if target.role == 'super_admin' and request.user.role != 'super_admin':
        messages.error(request, 'You do not have permission to modify a Super Admin.')
        return redirect('manage_users')

    action = request.POST.get('action', 'toggle')

    if action == 'activate':
        target.is_active = True
        target.save(update_fields=['is_active'])
        messages.success(request, f'{target.email} has been activated.')
    elif action == 'deactivate':
        target.is_active = False
        target.save(update_fields=['is_active'])
        messages.success(request, f'{target.email} has been deactivated.')
    else:
        # Toggle
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        status = 'activated' if target.is_active else 'deactivated'
        messages.success(request, f'{target.email} has been {status}.')

    return redirect('manage_users')


@login_required
def user_delete(request, user_id):
    """Hard-delete a user (with safety checks)."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.accounts.models import User

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    # Cannot delete yourself
    if target.id == request.user.id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('manage_users')

    # Cannot delete super_admin unless you are one
    if target.role == 'super_admin' and request.user.role != 'super_admin':
        messages.error(request, 'You do not have permission to delete a Super Admin.')
        return redirect('manage_users')

    if request.method == 'POST':
        confirm_email = (request.POST.get('confirm_email') or '').strip().lower()
        if confirm_email != target.email.lower():
            messages.error(request, 'Confirmation email does not match. Deletion cancelled.')
            return redirect('user_delete', user_id=target.id)

        email = target.email
        target.delete()
        messages.success(request, f'User "{email}" has been permanently deleted.')
        return redirect('manage_users')

    return render(request, 'dashboard/user_delete_confirm.html', {
        'target': target,
    })


@login_required
def user_change_role(request, user_id):
    """Change a user's role."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.accounts.models import User

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    if target.id == request.user.id:
        messages.error(request, 'You cannot change your own role.')
        return redirect('manage_users')

    if request.method == 'POST':
        new_role = request.POST.get('role', '').strip()

        # Allowed roles for school admin
        ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')

        if request.user.role != 'super_admin' and new_role not in ALLOWED_FOR_SCHOOL_ADMIN:
            messages.error(request, 'You are not allowed to assign that role.')
            return redirect('manage_users')

        if new_role not in dict(User.Role.choices):
            messages.error(request, 'Invalid role.')
            return redirect('manage_users')

        old_role = target.get_role_display()
        target.role = new_role
        target.save(update_fields=['role'])
        messages.success(
            request,
            f'{target.email} role changed from {old_role} to {target.get_role_display()}.'
        )
        return redirect('manage_users')

    # GET — render role selection
    role_choices = list(User.Role.choices)
    if request.user.role != 'super_admin':
        ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')
        role_choices = [(v, l) for v, l in role_choices if v in ALLOWED_FOR_SCHOOL_ADMIN]

    return render(request, 'dashboard/user_change_role.html', {
        'target': target,
        'role_choices': role_choices,
    })


# ==========================================================
# ACADEMICS
# ==========================================================

@login_required
def manage_classes(request):
    """Manage school classes — list, add, edit, delete."""
    if request.user.role not in ('school_admin', 'super_admin'):
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
    if request.user.role not in ('school_admin', 'super_admin'):
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

# ==========================================================
# TEACHER DASHBOARD & TOOLS
# ==========================================================


# ==========================================================
# TEACHER — MARK ATTENDANCE
# ==========================================================

    
# ==========================================================
# CLASS TEACHER DASHBOARD
# ==========================================================


# ==========================================================
# PARENT DASHBOARD & CHILD DETAIL
# ==========================================================

@login_required
def redirect_dashboard(request):
    """Send user to their own dashboard based on role."""
    role = request.user.role
    return redirect({
        'super_admin': 'dash_super_admin',
        'school_admin': 'dash_school_admin',
        'teacher': 'dash_teacher',
        'parent': 'dash_parent',
        'accountant': 'dash_accountant',
        'student': 'dash_student',
    }.get(role, 'landing'))
    

# ==========================================================
# ACCOUNTANT
# ==========================================================


# ==========================================================
# STUDENT DASHBOARD (No redirect loops)
# ==========================================================


# ==========================================================
# NOTIFICATIONS
# ==========================================================


@login_required
def mark_all_read(request):
    from apps.notifications.models import Notification
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications_list')


# ==========================================================
# BULK SMS
# ==========================================================


# ==========================================================
# SMART ALERTS DASHBOARD
# ==========================================================


# ==========================================================
# SUPER ADMIN — SCHOOLS MANAGEMENT
# ==========================================================


# ==========================================================
# SUBSCRIPTION
# ==========================================================

    # ==========================================================
# TIMETABLE
# ==========================================================

# School timetable periods — includes breaks as visual rows
TIMETABLE_PERIODS = [
    # ('start', 'end', 'type', 'label')
    # type: 'lesson' | 'short_break' | 'long_break' | 'lunch' | 'games'
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
    if request.user.role not in ('school_admin', 'super_admin'):
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
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.academics.models import Timetable

    entry = get_object_or_404(Timetable, id=entry_id, school=request.user.school)
    class_id = entry.class_level_id
    entry.delete()
    messages.success(request, 'Lesson removed.')
    return redirect(f'/dashboard/timetable/?class={class_id}')


    # ==========================================================
# ADD STUDENT (custom form)
# ==========================================================


# ==========================================================
# ACCOUNTANT — FULL TRANSACTIONS & ANALYTICS
# ==========================================================


    # ==========================================================
# TEST SMS
# ==========================================================


# ==========================================================
# BULK SMS
# ==========================================================

    # ==========================================================
# TIMETABLE PDF DOWNLOAD
# ==========================================================

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
# ==========================================================
# STUDENT CLEARANCE + LEAVING CERTIFICATE
# ==========================================================


# ==========================================================
# STUDENT BIO DATA PDF
# ==========================================================

# ==========================================================
# SUPER ADMIN — 3-MONTH PERFORMANCE REPORT
# ==========================================================

    # ==========================================================
# SUPER ADMIN — EDIT SCHOOL
# ==========================================================


# ==========================================================
# SUPER ADMIN — EDIT SCHOOL SUBSCRIPTION
# ==========================================================

    
    # ==========================================================
# INTERNAL MESSAGING — School Admin ↔ Teacher/Staff
# ==========================================================


# ==========================================================
# SUBSCRIPTION PAYMENT PENDING PAGES
# ==========================================================


# ==========================================================
# SUPER ADMIN — CONFIRM SUBSCRIPTION PAYMENT
# ==========================================================

    # ==========================================================
# ADD TEACHER
# ==========================================================


# ==========================================================
# ADD NON-TEACHING STAFF
# ==========================================================

@login_required
def add_staff(request):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff

    school = request.user.school

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        role = request.POST.get('role', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        date_of_birth = request.POST.get('date_of_birth') or None
        hire_date = request.POST.get('hire_date') or None
        salary = request.POST.get('salary') or None
        photo = request.FILES.get('photo')

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not id_number:
            errors.append('National ID is required.')
        if not role:
            errors.append('Role is required.')

        if NonTeachingStaff.objects.filter(school=school, id_number=id_number).exists():
            errors.append(f'Staff with ID "{id_number}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/add_staff.html', {
                'roles': NonTeachingStaff.Role.choices,
                'form_data': request.POST,
            })

        staff = NonTeachingStaff.objects.create(
            school=school,
            full_name=full_name,
            id_number=id_number,
            role=role,
            phone=phone,
            email=email,
            date_of_birth=date_of_birth,
            hire_date=hire_date,
            salary=salary,
            photo=photo,
        )

        messages.success(request, f'✅ Staff "{staff.full_name}" added successfully.')
        return redirect('staff_list')

    return render(request, 'dashboard/add_staff.html', {
        'roles': NonTeachingStaff.Role.choices,
    })


# ==========================================================
# DELETE TEACHER + STAFF
# ==========================================================


@login_required
def delete_staff(request, staff_id):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    staff = get_object_or_404(NonTeachingStaff, id=staff_id, school=request.user.school)

    if request.method == 'POST':
        name = staff.full_name
        staff.delete()
        messages.success(request, f'🗑️ Staff "{name}" deleted.')
        return redirect('staff_list')

    return render(request, 'dashboard/delete_staff.html', {'staff': staff})
# ==========================================================
# ADD PARENT
# ==========================================================


# ==========================================================
# DELETE PARENT
# ==========================================================


# ==========================================================
# LINK CHILDREN TO PARENT (Edit)
# ==========================================================

    # ==========================================================
# ACCOUNTANT — ALL STUDENTS WITH FEE BALANCES
# ==========================================================

    # ==========================================================
# ACCOUNTANT — CLASS FEE STATEMENT
# ==========================================================


# ==========================================================
# EXPENDITURE MANAGEMENT
# ==========================================================


# ==========================================================
# FEE STRUCTURE MANAGEMENT
# ==========================================================


    # ==========================================================
# FEE STRUCTURE MATRIX EDITOR
# ==========================================================


    # ==========================================================
# FEE STRUCTURE PDF
# ==========================================================

# ==========================================================
# CLASS TEACHER — Sub-views (stubs, filled in later messages)
# ==========================================================

# ==========================================================
# CLASS TEACHER — Attendance marking
# ==========================================================

# ==========================================================
# CLASS TEACHER — Grades entry + rankings
# ==========================================================


# ==========================================================
# ADMIN — Attendance Overview
# ==========================================================

    
    # ==========================================================
# ADMIN — Attendance views
# ==========================================================


# ==========================================================
# ADMIN — Absence Alerts list
# ==========================================================


# ==========================================================
# CLASS TEACHER — Bulk output (results sheet, report cards)
# ==========================================================


# ==========================================================
# STUDENT DETAIL — Admin / Teacher / Accountant view
# ==========================================================

@login_required
def subject_delete(request, subject_id):
    """Confirm and delete a subject."""
    if request.user.role not in ('school_admin', 'super_admin'):
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
    # ==========================================================
# SUBSCRIPTION PLANS — progressive disclosure flow
# ==========================================================


