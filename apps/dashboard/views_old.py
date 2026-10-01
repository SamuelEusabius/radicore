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
@login_required
def super_admin_dash(request):
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription
    return render(request, 'dashboard/super_admin.html', {
        'school_count': School.objects.count(),
        'active_count': School.objects.filter(is_active=True).count(),
        'inactive_count': School.objects.filter(is_active=False).count(),
        'pending_payments': SchoolSubscription.objects.filter(
            status='pending_payment'
        ).select_related('school', 'plan'),
    })

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
def manage_users(request):
    """List users with filters, search, and role breakdown."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.accounts.models import User
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    # ---------- Base queryset ----------
    if request.user.role == 'super_admin':
        base_qs = User.objects.all().select_related('school')
    else:
        base_qs = User.objects.filter(school=request.user.school)

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs.order_by('role', 'email')

    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )

    if role_filter:
        qs = qs.filter(role=role_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # ---------- Stats (unfiltered) ----------
    stats = {
        'total': base_qs.count(),
        'teachers': base_qs.filter(role='teacher').count(),
        'school_admins': base_qs.filter(role='school_admin').count(),
        'accountants': base_qs.filter(role='accountant').count(),
        'parents': base_qs.filter(role='parent').count(),
        'students': base_qs.filter(role='student').count(),
        'staff': base_qs.filter(role='staff').count(),
        'super_admins': base_qs.filter(role='super_admin').count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ---------- Role choices ----------
    from apps.accounts.models import User as U
    role_choices = list(U.Role.choices)
    if request.user.role != 'super_admin':
        ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')
        role_choices = [(v, l) for v, l in role_choices if v in ALLOWED_FOR_SCHOOL_ADMIN]

    return render(request, 'dashboard/manage_users.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': role_choices,
        'total_filtered': qs.count(),
        'is_super_admin': request.user.role == 'super_admin',
    })


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

@login_required
def create_user(request):
    """Create a new user."""
    if not request.user.is_authenticated:
        return redirect('/accounts/login/')

    if getattr(request.user, 'role', None) not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')

    import secrets
    import string

    def generate_password(length=10):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    generated_password = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        # If user clicked "Generate" — auto-create password
        if request.POST.get('auto_password') == '1' or not password:
            password = generate_password()
            generated_password = password

        # Server-side role guard
        if not email or not role:
            messages.error(request, 'Email and role are required.')
        elif request.user.role != 'super_admin' and role not in ALLOWED_FOR_SCHOOL_ADMIN:
            messages.error(
                request,
                f'You are not allowed to create a "{role.replace("_", " ").title()}" account.'
            )
        elif User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            # School assignment
            if request.user.role == 'super_admin':
                school_id = request.POST.get('school_id')
                if school_id:
                    from apps.schools.models import School
                    assigned_school = School.objects.filter(id=school_id).first() or request.user.school
                else:
                    assigned_school = request.user.school
            else:
                assigned_school = request.user.school

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                school=assigned_school,
            )
            messages.success(
                request,
                f'{role.replace("_", " ").title()} "{email}" created successfully.'
            )

            if generated_password:
                messages.info(
                    request,
                    f'Auto-generated password: {generated_password} — share this with the user securely.'
                )

            return redirect('manage_users')

    # Role choices
    if request.user.role == 'super_admin':
        role_choices = [r for r in User.Role.choices if r[0] != 'super_admin']
    else:
        role_choices = [r for r in User.Role.choices if r[0] in ALLOWED_FOR_SCHOOL_ADMIN]

    schools = None
    if request.user.role == 'super_admin':
        from apps.schools.models import School
        schools = School.objects.filter(is_active=True).order_by('name')

    return render(request, 'dashboard/create_user.html', {
        'roles': role_choices,
        'schools': schools,
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

@login_required
def schools_manage(request):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    from django.db import models

    schools = School.objects.all().order_by('name')

    search = request.GET.get('q', '').strip()
    if search:
        schools = schools.filter(
            models.Q(name__icontains=search) |
            models.Q(code__icontains=search) |
            models.Q(nemis_code__icontains=search) |
            models.Q(county__icontains=search)
        )

    return render(request, 'dashboard/schools_manage.html', {
        'schools': schools,
        'search': search,
        'total': schools.count(),
    })


@login_required
def school_add(request):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        county = request.POST.get('county', '').strip()
        sub_county = request.POST.get('sub_county', '').strip()
        nemis_code = request.POST.get('nemis_code', '').strip()
        school_type = request.POST.get('school_type', 'private')
        gender = request.POST.get('gender', 'mixed')
        level = request.POST.get('level', 'all')
        motto = request.POST.get('motto', '').strip()
        physical_address = request.POST.get('physical_address', '').strip()
        blocked_message = request.POST.get('blocked_message', '').strip()

        admin_email = request.POST.get('admin_email', '').strip()
        admin_password = request.POST.get('admin_password', '').strip()
        admin_first_name = request.POST.get('admin_first_name', '').strip()
        admin_last_name = request.POST.get('admin_last_name', '').strip()

        errors = []
        if not name:
            errors.append('School name is required.')
        if not admin_email:
            errors.append('Admin email is required.')
        if not admin_password:
            errors.append('Admin password is required.')
        if School.objects.filter(name=name).exists():
            errors.append(f'A school named "{name}" already exists.')
        if User.objects.filter(email=admin_email).exists():
            errors.append(f'Email "{admin_email}" is already registered.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/school_add.html', {'form_data': request.POST})

        school = School.objects.create(
            name=name, email=email, phone=phone,
            county=county, sub_county=sub_county, nemis_code=nemis_code,
            school_type=school_type, gender=gender, level=level,
            motto=motto, physical_address=physical_address,
            blocked_message=blocked_message or None,
            is_active=True,
        )

        User.objects.create_user(
            username=admin_email, email=admin_email, password=admin_password,
            first_name=admin_first_name, last_name=admin_last_name,
            role='school_admin', school=school,
        )

        messages.success(request, f'School "{school.name}" created with code {school.code}.')
        return redirect('schools_manage')

    return render(request, 'dashboard/school_add.html')


@login_required
def school_toggle_active(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        school.is_active = not school.is_active
        school.save()
        status = 'activated' if school.is_active else 'deactivated'
        messages.success(request, f'{school.name} has been {status}.')
    return redirect('schools_manage')


@login_required
def school_change_admin_password(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)
    admins = User.objects.filter(school=school, role='school_admin')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_password = request.POST.get('new_password', '').strip()

        if not user_id or not new_password:
            messages.error(request, 'Select an admin and enter a new password.')
        elif len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            try:
                admin = admins.get(id=user_id)
                admin.set_password(new_password)
                admin.save()
                messages.success(request, f'Password changed for {admin.email}.')
                return redirect('schools_manage')
            except User.DoesNotExist:
                messages.error(request, 'Admin not found.')

    return render(request, 'dashboard/school_change_password.html', {
        'school': school, 'admins': admins,
    })


@login_required
def school_delete(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        name = school.name
        school.delete()
        messages.success(request, f'School "{name}" has been permanently deleted.')
        return redirect('schools_manage')

    return render(request, 'dashboard/school_delete.html', {'school': school})


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

@login_required
def super_admin_performance(request):
    """Show platform-wide performance metrics for the last 3 months."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription
    from apps.accounts.models import User
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.parents.models import Parent
    from apps.staff.models import NonTeachingStaff
    from apps.finance.models import Payment, Invoice
    from apps.notifications.models import Alert
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncMonth

    now = timezone.now()
    three_months_ago = now - timedelta(days=90)

    # ---------- OVERALL TOTALS ----------
    total_schools = School.objects.count()
    active_schools = School.objects.filter(is_active=True).count()
    total_users = User.objects.count()
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_parents = Parent.objects.count()
    total_staff = NonTeachingStaff.objects.filter(is_active=True).count()

    # ---------- 3-MONTH METRICS ----------
    # Schools registered in last 3 months
    schools_3m = School.objects.filter(created_at__gte=three_months_ago).count()

    # Users registered in last 3 months
    users_3m = User.objects.filter(date_joined__gte=three_months_ago).count()

    # Payments (fees collected) in last 3 months
    payments_3m = Payment.objects.filter(
        paid_at__gte=three_months_ago
    ).aggregate(total=Sum('amount_kes'))['total'] or 0

    # Invoices created in last 3 months
    invoices_3m = Invoice.objects.filter(
        created_at__gte=three_months_ago
    ).aggregate(total=Sum('amount_due'))['total'] or 0

    # Alerts in last 3 months
    alerts_3m = Alert.objects.filter(created_at__gte=three_months_ago).count()
    critical_alerts = Alert.objects.filter(
        created_at__gte=three_months_ago,
        severity='critical',
        status='new'
    ).count()

    # ---------- MONTHLY BREAKDOWN ----------
    monthly_schools = (
        School.objects.filter(created_at__gte=three_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    monthly_users = (
        User.objects.filter(date_joined__gte=three_months_ago)
        .annotate(month=TruncMonth('date_joined'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    monthly_payments = (
        Payment.objects.filter(paid_at__gte=three_months_ago)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount_kes'))
        .order_by('month')
    )

    # ---------- PERFORMANCE SCORES ----------
    # 4 service performance indicators (0-100%)

    # 1. School activation rate (active / total)
    activation_rate = round((active_schools / total_schools * 100), 1) if total_schools else 0

    # 2. Data richness (avg students per active school)
    avg_students_per_school = round(total_students / active_schools, 1) if active_schools else 0
    # Score: students per school relative to target of 200
    student_score = min(round((avg_students_per_school / 200) * 100, 1), 100)

    # 3. Financial activity (collections / expected invoices)
    financial_score = round((float(payments_3m) / float(invoices_3m) * 100), 1) if invoices_3m else 0
    financial_score = min(financial_score, 100)

    # 4. System health (low alerts = high score)
    # 100 - (alerts per school) * 5, floor at 0
    if active_schools:
        alert_ratio = (alerts_3m / active_schools) * 5
        health_score = max(round(100 - alert_ratio, 1), 0)
    else:
        health_score = 100

    # 5. User engagement (active users / total)
    engagement_score = round((users_3m / total_users * 100), 1) if total_users else 0
    engagement_score = min(engagement_score, 100)

    # Overall score
    overall_score = round(
        (activation_rate + student_score + financial_score + health_score + engagement_score) / 5, 1
    )

    # ---------- PREPARE CHART DATA ----------
    # Last 3 months labels (e.g., ["Jul 2026", "Aug 2026", "Sep 2026"])
    month_labels = []
    month_schools_data = []
    month_users_data = []
    month_payments_data = []

    for i in range(2, -1, -1):
        m = (now - timedelta(days=30 * i)).replace(day=1)
        label = m.strftime('%b %Y')
        month_labels.append(label)

        # Count schools that month
        month_start = m
        if i > 0:
            month_end = (now - timedelta(days=30 * (i - 1))).replace(day=1)
        else:
            month_end = now

        month_schools_data.append(
            School.objects.filter(created_at__gte=month_start, created_at__lt=month_end).count()
        )
        month_users_data.append(
            User.objects.filter(date_joined__gte=month_start, date_joined__lt=month_end).count()
        )
        payments_total = Payment.objects.filter(
            paid_at__gte=month_start, paid_at__lt=month_end
        ).aggregate(total=Sum('amount_kes'))['total'] or 0
        month_payments_data.append(float(payments_total))

    return render(request, 'dashboard/super_admin_performance.html', {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'total_users': total_users,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_parents': total_parents,
        'total_staff': total_staff,
        'schools_3m': schools_3m,
        'users_3m': users_3m,
        'payments_3m': payments_3m,
        'invoices_3m': invoices_3m,
        'alerts_3m': alerts_3m,
        'critical_alerts': critical_alerts,

        # Scores
        'activation_rate': activation_rate,
        'student_score': student_score,
        'financial_score': financial_score,
        'health_score': health_score,
        'engagement_score': engagement_score,
        'overall_score': overall_score,

        # Chart data (JSON-safe)
        'month_labels': month_labels,
        'month_schools_data': month_schools_data,
        'month_users_data': month_users_data,
        'month_payments_data': month_payments_data,
    })
    # ==========================================================
# SUPER ADMIN — EDIT SCHOOL
# ==========================================================

@login_required
def school_edit(request, school_id):
    """Super Admin edits school details + uploads logo."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, SubscriptionPlan, BoardMember

    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        # ---------- Basic info ----------
        school.name = request.POST.get('name', '').strip() or school.name
        school.email = request.POST.get('email', '').strip()
        school.phone = request.POST.get('phone', '').strip()
        school.motto = request.POST.get('motto', '').strip()
        school.county = request.POST.get('county', '').strip()
        school.sub_county = request.POST.get('sub_county', '').strip()
        school.ward = request.POST.get('ward', '').strip()
        school.physical_address = request.POST.get('physical_address', '').strip()
        school.postal_address = request.POST.get('postal_address', '').strip()
        school.nemis_code = request.POST.get('nemis_code', '').strip()

        # ---------- Classification ----------
        school.school_type = request.POST.get('school_type', 'private')
        school.gender = request.POST.get('gender', 'mixed')
        school.level = request.POST.get('level', 'all')

        # ---------- Status ----------
        school.is_active = request.POST.get('is_active') == 'on'

        # ---------- Subscription ----------
        plan_id = request.POST.get('plan')
        if plan_id:
            school.plan = SubscriptionPlan.objects.filter(id=plan_id).first()

        # ---------- Leadership ----------
        school.principal_name = request.POST.get('principal_name', '').strip()
        school.principal_id = request.POST.get('principal_id', '').strip()
        school.principal_phone = request.POST.get('principal_phone', '').strip()
        school.principal_email = request.POST.get('principal_email', '').strip()

        school.deputy_name = request.POST.get('deputy_name', '').strip()
        school.deputy_id = request.POST.get('deputy_id', '').strip()
        school.deputy_phone = request.POST.get('deputy_phone', '').strip()
        school.deputy_email = request.POST.get('deputy_email', '').strip()

        school.senior_teacher_name = request.POST.get('senior_teacher_name', '').strip()
        school.senior_teacher_id = request.POST.get('senior_teacher_id', '').strip()
        school.senior_teacher_phone = request.POST.get('senior_teacher_phone', '').strip()
        school.senior_teacher_email = request.POST.get('senior_teacher_email', '').strip()

        school.accountant_name = request.POST.get('accountant_name', '').strip()
        school.accountant_id = request.POST.get('accountant_id', '').strip()
        school.accountant_phone = request.POST.get('accountant_phone', '').strip()
        school.accountant_email = request.POST.get('accountant_email', '').strip()

        # ---------- Logo upload ----------
        if 'logo' in request.FILES:
            school.logo = request.FILES['logo']

        # ---------- Leadership photos ----------
        if 'principal_photo' in request.FILES:
            school.principal_photo = request.FILES['principal_photo']
        if 'deputy_photo' in request.FILES:
            school.deputy_photo = request.FILES['deputy_photo']
        if 'senior_teacher_photo' in request.FILES:
            school.senior_teacher_photo = request.FILES['senior_teacher_photo']
        if 'accountant_photo' in request.FILES:
            school.accountant_photo = request.FILES['accountant_photo']

        # ---------- Remove logo ----------
        if request.POST.get('remove_logo') == 'on':
            school.logo.delete(save=False)
            school.logo = None

        school.save()
        messages.success(request, f'✅ School "{school.name}" updated successfully.')
        return redirect('schools_manage')

    # GET — show form
    plans = SubscriptionPlan.objects.all().order_by('order', 'min_students')
    board_members = school.board_members.all()

    return render(request, 'dashboard/school_edit.html', {
        'school': school,
        'plans': plans,
        'board_members': board_members,
    })


@login_required
def school_remove_logo(request, school_id):
    """Quick action to remove a school's logo."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)
    school.logo.delete(save=False)
    school.logo = None
    school.save()
    messages.success(request, f'Logo removed for {school.name}.')
    return redirect('school_edit', school_id=school.id)


@login_required
def board_member_add(request, school_id):
    """Add a board member to a school."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, BoardMember
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        BoardMember.objects.create(
            school=school,
            full_name=request.POST.get('full_name', '').strip(),
            id_number=request.POST.get('id_number', '').strip(),
            occupation=request.POST.get('occupation', '').strip(),
            role=request.POST.get('role', 'member'),
            phone=request.POST.get('phone', '').strip(),
            email=request.POST.get('email', '').strip(),
            photo=request.FILES.get('photo'),
        )
        messages.success(request, 'Board member added.')
        return redirect('school_edit', school_id=school.id)

    return render(request, 'dashboard/board_member_form.html', {
        'school': school,
        'roles': BoardMember.Role.choices,
    })


@login_required
def board_member_delete(request, member_id):
    """Delete a board member."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import BoardMember
    member = get_object_or_404(BoardMember, id=member_id)
    school_id = member.school.id
    member.delete()
    messages.success(request, 'Board member removed.')
    return redirect('school_edit', school_id=school_id)
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


@login_required
def admin_student_detail(request, student_id):
    """Placeholder — will show student detail for admin."""
    messages.info(request, 'Student detail view coming soon.')
    return redirect('admin_attendance_overview')


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


