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

    
@login_required
def manage_exams(request):
    if request.user.role not in ('teacher', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.grades.models import Exam

    if request.method == 'POST':
        name = request.POST.get('name')
        term = request.POST.get('term')
        year = request.POST.get('year')
        if name and term and year:
            Exam.objects.get_or_create(
                school=request.user.school, name=name, term=term, year=year
            )
            messages.success(request, f'Exam "{name}" created.')
        return redirect('manage_exams')

    exams = Exam.objects.filter(school=request.user.school).order_by('-year', '-id')
    return render(request, 'dashboard/manage_exams.html', {'exams': exams})


@login_required
def enter_grades(request):
    if request.user.role not in ('teacher', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.grades.models import Exam, Grade
    from apps.academics.models import Subject
    from apps.students.models import Student

    school = request.user.school
    exams = Exam.objects.filter(school=school).order_by('-year', '-id')
    subjects = Subject.objects.filter(school=school)
    students = Student.objects.filter(school=school, is_active=True)

    exam_id = request.GET.get('exam')
    subject_id = request.GET.get('subject')

    selected_exam = None
    selected_subject = None
    rows = []

    if exam_id and subject_id:
        try:
            selected_exam = Exam.objects.get(id=exam_id, school=school)
            selected_subject = Subject.objects.get(id=subject_id, school=school)

            existing = {g.student_id: g for g in Grade.objects.filter(
                exam=selected_exam, subject=selected_subject
            )}

            rows = [{
                'student': s,
                'marks': existing[s.id].marks if s.id in existing else '',
                'out_of': existing[s.id].out_of if s.id in existing else 100,
                'remarks': existing[s.id].remarks if s.id in existing else '',
            } for s in students]

            if request.method == 'POST':
                saved = 0
                for s in students:
                    marks = request.POST.get(f'marks_{s.id}', '').strip()
                    if not marks:
                        continue
                    try:
                        marks_val = float(marks)
                    except ValueError:
                        continue

                    Grade.objects.update_or_create(
                        exam=selected_exam, subject=selected_subject, student=s,
                        defaults={
                            'marks': marks_val,
                            'out_of': float(request.POST.get(f'out_of_{s.id}', 100) or 100),
                            'remarks': request.POST.get(f'remarks_{s.id}', ''),
                        })
                    saved += 1

                messages.success(request, f'{saved} grades saved.')
                return redirect(f'/dashboard/grades/enter/?exam={exam_id}&subject={subject_id}')

        except (Exam.DoesNotExist, Subject.DoesNotExist):
            messages.error(request, 'Invalid exam or subject.')

    return render(request, 'dashboard/enter_grades.html', {
        'exams': exams,
        'subjects': subjects,
        'rows': rows,
        'selected_exam': selected_exam,
        'selected_subject': selected_subject,
    })


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

@login_required
@accountant_only
def accountant_dash(request):
    from django.db.models import Sum, Count, F
    from django.db.models.functions import TruncMonth
    from django.utils import timezone
    from datetime import timedelta
    from apps.finance.models import Invoice, Payment
    from apps.students.models import Student

    school = request.user.school

    # ---------- Invoices: aggregate in the DB ----------
    invoice_qs = Invoice.objects.filter(student__school=school)

    agg = invoice_qs.aggregate(
        total_invoiced=Sum('amount_due'),
        total_paid=Sum('amount_paid'),
        invoice_count=Count('id'),
    )

    total_invoiced = agg['total_invoiced'] or 0
    total_paid     = agg['total_paid'] or 0
    outstanding    = total_invoiced - total_paid
    invoice_count  = agg['invoice_count'] or 0

    collection_rate = round(
        (float(total_paid) / float(total_invoiced) * 100) if total_invoiced else 0,
        1
    )

    # ---------- Status counts (single grouped query) ----------
    status_counts = dict(
        invoice_qs.values_list('status').annotate(c=Count('id'))
    )
    overdue_count = status_counts.get('overdue', 0)
    unpaid_count  = status_counts.get('unpaid', 0)

    # ---------- Recent payments (5 latest) ----------
    recent_payments = (
        Payment.objects
        .filter(invoice__student__school=school)
        .select_related('invoice__student')
        .order_by('-paid_at')[:5]
    )

    # ---------- Collections trend: last 6 months ----------
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_rows = (
        Payment.objects
        .filter(invoice__student__school=school, paid_at__gte=six_months_ago)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount_kes'))
        .order_by('month')
    )

    totals_by_month = {
        row['month'].strftime('%Y-%m'): float(row['total'] or 0)
        for row in monthly_rows if row['month']
    }

    today = timezone.now().replace(day=1)
    chart_labels = []
    chart_values = []
    for i in range(5, -1, -1):
        m = (today - timedelta(days=30 * i))
        key = m.strftime('%Y-%m')
        chart_labels.append(m.strftime('%b'))
        chart_values.append(totals_by_month.get(key, 0))

    # ---------- Top 5 debtors (biggest outstanding balances) ----------
    top_debtors = (
        Student.objects
        .filter(school=school, is_active=True, invoices__isnull=False)
        .annotate(
            total_due=Sum('invoices__amount_due'),
            total_paid=Sum('invoices__amount_paid'),
        )
        .annotate(balance=F('total_due') - F('total_paid'))
        .filter(balance__gt=0)
        .order_by('-balance')[:5]
    )
        # ---------- Payment method breakdown (this month) ----------
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    method_rows = (
        Payment.objects
        .filter(
            invoice__student__school=school,
            paid_at__gte=month_start,
        )
        .values('method')
        .annotate(total=Sum('amount_kes'))
        .order_by('-total')
    )

    method_labels = dict(Payment.Method.choices)
    method_total = sum(float(r['total'] or 0) for r in method_rows)

    method_breakdown = []
    for r in method_rows:
        total = float(r['total'] or 0)
        method_breakdown.append({
            'code': r['method'],
            'label': method_labels.get(r['method'], r['method']),
            'total': total,
            'pct': round((total / method_total) * 100, 1) if method_total else 0,
        })

    return render(request, 'dashboard/accountant.html', {
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'invoice_count': invoice_count,
        'overdue_count': overdue_count,
        'unpaid_count': unpaid_count,
        'collection_rate': collection_rate,
        'recent_payments': recent_payments,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'top_debtors': top_debtors,
        'method_breakdown': method_breakdown,
        'method_total': method_total,
    })

@login_required
def accountant_invoices(request):
    """Invoice list with status tabs, search, filters, and pagination."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, FeeStructure
    from apps.students.models import Student
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    school = request.user.school

    base_qs = Invoice.objects.filter(
        student__school=school
    ).select_related('student', 'fee_structure')

    # ---------- Stats (unfiltered) ----------
    stats_agg = base_qs.aggregate(
        total=Count('id'),
        paid=Count('id', filter=Q(status='paid')),
        partial=Count('id', filter=Q(status='partial')),
        unpaid=Count('id', filter=Q(status='unpaid')),
        overdue=Count('id', filter=Q(status='overdue')),
    )

    # ---------- Filters ----------
    qs = base_qs.order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    if status_filter in ('paid', 'partial', 'unpaid', 'overdue'):
        qs = qs.filter(status=status_filter)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__middle_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__admission_number__icontains=search) |
            Q(fee_structure__name__icontains=search)
        )

    term_filter = request.GET.get('term', '').strip()
    if term_filter:
        qs = qs.filter(fee_structure__name__startswith=f"{term_filter} —")

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ---------- Term choices for filter ----------
    all_fs = FeeStructure.objects.filter(school=school).values_list('name', flat=True)
    terms = set()
    for name in all_fs:
        if ' — ' in name:
            terms.add(name.split(' — ', 1)[0])
        else:
            terms.add(name)
    term_choices = sorted(terms)

    return render(request, 'dashboard/accountant_invoices.html', {
        'invoices': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats_agg,
        'status_filter': status_filter,
        'search': search,
        'term_filter': term_filter,
        'term_choices': term_choices,
        'total_filtered': qs.count(),
    })

@login_required
def generate_invoices(request):
    """
    Generate invoices in 3 modes:
      - Single student (custom or class-default amount)
      - Single class (all active students)
      - All classes (bulk by term)
    """
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import FeeStructure, Invoice
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from django.db import transaction
    from collections import defaultdict
    from decimal import Decimal

    school = request.user.school

    # ---- Group fee structures by term ----
    all_fs = FeeStructure.objects.filter(school=school).order_by('name')
    terms = defaultdict(list)
    for fs in all_fs:
        term_part = fs.name.split(' — ', 1)[0] if ' — ' in fs.name else fs.name
        terms[term_part].append(fs)
    term_choices = sorted(terms.keys())

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # ---- Helper: compute total fee for a class + term ----
    def class_term_total(class_name, term_prefix):
        qs = FeeStructure.objects.filter(
            school=school,
            class_level=class_name,
            name__startswith=f"{term_prefix} —",
        )
        if not qs.exists():
            return None, None, None
        total = sum(float(f.amount_kes) for f in qs)
        anchor = qs.first()
        return float(total), anchor, anchor.due_date

    # ==========================================================
    # POST — do the generation
    # ==========================================================
    if request.method == 'POST':
        mode = request.POST.get('mode', 'bulk')
        term_name = request.POST.get('term', '').strip()
        custom_term = request.POST.get('custom_term', '').strip()
        term_prefix = custom_term or term_name

        if not term_prefix:
            messages.error(request, 'Please select or type a term.')
            return redirect('generate_invoices')

        # ---------------------------------------------------
        # MODE: SINGLE STUDENT
        # ---------------------------------------------------
        if mode == 'single':
            student_id = request.POST.get('student_id')
            custom_amount = request.POST.get('custom_amount', '').strip()
            override_amount = request.POST.get('override_amount', '').strip()

            try:
                student = Student.objects.get(
                    id=student_id, school=school, is_active=True
                )
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')
                return redirect('generate_invoices')

            # Determine amount
            if override_amount and custom_amount:
                # Custom amount from modal
                try:
                    amount = float(custom_amount)
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid custom amount.')
                    return redirect('generate_invoices')
                # Use first matching FS as anchor if available
                anchor = FeeStructure.objects.filter(
                    school=school, class_level=student.class_level,
                    name__startswith=f"{term_prefix} —"
                ).first()
                if not anchor:
                    messages.error(
                        request,
                        f'No fee structure exists for {student.class_level} — '
                        f'please use matrix draft first.'
                    )
                    return redirect('generate_invoices')
                due_date = anchor.due_date
            else:
                # Use class default
                amount, anchor, due_date = class_term_total(
                    student.class_level, term_prefix
                )
                if amount is None:
                    messages.error(
                        request,
                        f'No fee structure for {student.class_level} '
                        f'in term "{term_prefix}".'
                    )
                    return redirect('generate_invoices')

            invoice, created = Invoice.objects.get_or_create(
                student=student,
                fee_structure=anchor,
                defaults={'amount_due': amount, 'due_date': due_date},
            )
            if created:
                messages.success(
                    request,
                    f'✅ Invoice created for {student.full_name}: '
                    f'KES {amount:,.0f} ({term_prefix}).'
                )
            else:
                invoice.amount_due = amount
                invoice.due_date = due_date
                invoice.save(update_fields=['amount_due', 'due_date'])
                invoice.update_status()
                messages.info(
                    request,
                    f'Invoice updated for {student.full_name}: '
                    f'KES {amount:,.0f}.'
                )
            return redirect('accountant_invoices')

        # ---------------------------------------------------
        # MODE: SINGLE CLASS
        # ---------------------------------------------------
        if mode == 'class':
            class_name = request.POST.get('class_name', '').strip()
            if not class_name:
                messages.error(request, 'Please pick a class.')
                return redirect('generate_invoices')

            amount, anchor, due_date = class_term_total(class_name, term_prefix)
            if amount is None:
                messages.error(
                    request,
                    f'No fee structure for {class_name} in "{term_prefix}".'
                )
                return redirect('generate_invoices')

            students = Student.objects.filter(
                school=school, class_level=class_name, is_active=True,
            )

            created_count = 0
            updated_count = 0
            total_billed = 0

            with transaction.atomic():
                for s in students:
                    inv, was_created = Invoice.objects.get_or_create(
                        student=s,
                        fee_structure=anchor,
                        defaults={'amount_due': amount, 'due_date': due_date},
                    )
                    if was_created:
                        created_count += 1
                        total_billed += amount
                    elif float(inv.amount_due) != amount:
                        inv.amount_due = amount
                        inv.due_date = due_date
                        inv.save(update_fields=['amount_due', 'due_date'])
                        inv.update_status()
                        updated_count += 1

            msg = f'✅ {class_name} ({term_prefix}): {created_count} created'
            if updated_count:
                msg += f', {updated_count} updated'
            msg += f'. Total billed: KES {total_billed:,.0f}.'
            messages.success(request, msg)
            return redirect('accountant_invoices')

        # ---------------------------------------------------
        # MODE: ALL CLASSES (bulk)
        # ---------------------------------------------------
        matching_fs = FeeStructure.objects.filter(
            school=school,
            name__startswith=f"{term_prefix} —",
        )

        if not matching_fs.exists():
            messages.error(
                request, f'No fee structures found for term "{term_prefix}".'
            )
            return redirect('generate_invoices')

        by_class = defaultdict(list)
        for fs in matching_fs:
            by_class[fs.class_level].append(fs)

        created_count = 0
        updated_count = 0
        classes_processed = 0
        total_billed = 0

        with transaction.atomic():
            for class_name, fee_list in by_class.items():
                total_fee = sum(float(f.amount_kes) for f in fee_list)
                if total_fee <= 0:
                    continue

                anchor_fs = fee_list[0]
                due_date = anchor_fs.due_date

                students = Student.objects.filter(
                    school=school, class_level=class_name, is_active=True,
                )

                for student in students:
                    inv, was_created = Invoice.objects.get_or_create(
                        student=student,
                        fee_structure=anchor_fs,
                        defaults={'amount_due': total_fee, 'due_date': due_date},
                    )
                    if was_created:
                        created_count += 1
                        total_billed += total_fee
                    elif float(inv.amount_due) != total_fee:
                        inv.amount_due = total_fee
                        inv.due_date = due_date
                        inv.save(update_fields=['amount_due', 'due_date'])
                        inv.update_status()
                        updated_count += 1

                classes_processed += 1

        msg = f'✅ Bulk ({term_prefix}): {created_count} created'
        if updated_count:
            msg += f', {updated_count} updated'
        msg += f' across {classes_processed} classes.'
        messages.success(request, msg)
        return redirect('accountant_invoices')

    # ==========================================================
    # GET — render form + optional preview
    # ==========================================================
    preview_term = request.GET.get('term', '').strip()

    preview = None
    if preview_term:
        matching = FeeStructure.objects.filter(
            school=school, name__startswith=f"{preview_term} —"
        )
        by_class = defaultdict(lambda: {'items': [], 'total': 0.0, 'due_date': None})
        for fs in matching:
            by_class[fs.class_level]['items'].append({
                'name': fs.name.split(' — ', 1)[-1] if ' — ' in fs.name else fs.name,
                'amount': float(fs.amount_kes),
            })
            by_class[fs.class_level]['total'] += float(fs.amount_kes)
            if not by_class[fs.class_level]['due_date']:
                by_class[fs.class_level]['due_date'] = fs.due_date

        preview_classes = []
        grand_total = 0
        total_students = 0
        for class_name, data in by_class.items():
            count = Student.objects.filter(
                school=school, class_level=class_name, is_active=True
            ).count()
            if count == 0:
                continue
            class_total = data['total'] * count
            grand_total += class_total
            total_students += count
            preview_classes.append({
                'class_name': class_name,
                'items': data['items'],
                'per_student': data['total'],
                'student_count': count,
                'class_total': class_total,
                'due_date': data['due_date'],
            })
        preview_classes.sort(key=lambda x: x['class_name'])

        preview = {
            'term': preview_term,
            'classes': preview_classes,
            'total_students': total_students,
            'grand_total': grand_total,
        }

       # Students for single-student dropdown
    all_students = Student.objects.filter(
        school=school, is_active=True
    ).order_by('class_level', 'first_name', 'last_name')

    return render(request, 'dashboard/generate_invoices.html', {
        'term_choices': term_choices,
        'classes': classes,
        'students': all_students,
        'preview': preview,
        'preview_term': preview_term,
    })
    
# ==========================================================
# STUDENT DASHBOARD (No redirect loops)
# ==========================================================


# ==========================================================
# NOTIFICATIONS
# ==========================================================
@login_required
def notifications_list(request):
    """List user's notifications with filters and grouping."""
    from apps.notifications.models import Notification
    from django.db.models import Q, Count
    from django.core.paginator import Paginator
    from datetime import timedelta
    from django.utils import timezone

    base_qs = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    channel_filter = request.GET.get('channel', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(message__icontains=search) |
            Q(description__icontains=search)
        )

    if channel_filter in ('email', 'sms', 'in_app'):
        qs = qs.filter(channel=channel_filter)

    if status_filter == 'unread':
        qs = qs.filter(is_read=False)
    elif status_filter == 'read':
        qs = qs.filter(is_read=True)

    # ---------- Stats ----------
    stats = {
        'total': base_qs.count(),
        'unread': base_qs.filter(is_read=False).count(),
        'in_app': base_qs.filter(channel='in_app').count(),
        'sms': base_qs.filter(channel='sms').count(),
        'email': base_qs.filter(channel='email').count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ---------- Group by date ----------
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = {
        'today': [],
        'yesterday': [],
        'this_week': [],
        'older': [],
    }

    for n in page_obj:
        n_date = n.created_at.date()
        if n_date == today:
            groups['today'].append(n)
        elif n_date == yesterday:
            groups['yesterday'].append(n)
        elif n_date >= week_ago:
            groups['this_week'].append(n)
        else:
            groups['older'].append(n)

    return render(request, 'dashboard/notifications.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'groups': groups,
        'search': search,
        'channel_filter': channel_filter,
        'status_filter': status_filter,
        'total_filtered': qs.count(),
    })

@login_required
def mark_notification_read(request, notif_id):
    from apps.notifications.models import Notification
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return redirect('notifications_list')


@login_required
def mark_all_read(request):
    from apps.notifications.models import Notification
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications_list')


# ==========================================================
# BULK SMS
# ==========================================================

@login_required
@login_required
def class_results(request):
    if request.user.role not in ('teacher', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student

    user = request.user
    school = user.school

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    exams = Exam.objects.filter(school=school).order_by('-year', '-id')

    class_id = request.GET.get('class')
    exam_id = request.GET.get('exam')

    selected_class = None
    selected_exam = None
    results = []

    if not class_id and classes.exists():
        class_id = classes.first().id
    if not exam_id and exams.exists():
        exam_id = exams.first().id

    if class_id and exam_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
            selected_exam = Exam.objects.get(id=exam_id, school=school)
        except (ClassLevel.DoesNotExist, Exam.DoesNotExist):
            pass

    if selected_class and selected_exam:
        students = Student.objects.filter(
            school=school,
            class_level=selected_class.name,
            is_active=True,
        )

        grades_qs = Grade.objects.filter(
            exam=selected_exam,
            student__in=students,
        ).select_related('subject', 'student')

        student_data = {}
        for g in grades_qs:
            sid = g.student_id
            if sid not in student_data:
                student_data[sid] = {
                    'student': g.student,
                    'marks': 0,
                    'out_of': 0,
                    'subjects': [],
                }
            student_data[sid]['marks'] += float(g.marks)
            student_data[sid]['out_of'] += float(g.out_of)
            student_data[sid]['subjects'].append(g)

        for sid, data in student_data.items():
            if data['out_of'] > 0:
                data['avg'] = round((data['marks'] / data['out_of']) * 100, 1)
            else:
                data['avg'] = 0

            avg = data['avg']
            if avg >= 80:
                data['cbc'] = 'EE'
                data['cbc_label'] = 'Exceeding Expectation'
            elif avg >= 65:
                data['cbc'] = 'ME'
                data['cbc_label'] = 'Meeting Expectation'
            elif avg >= 50:
                data['cbc'] = 'AE'
                data['cbc_label'] = 'Approaching Expectation'
            else:
                data['cbc'] = 'BE'
                data['cbc_label'] = 'Below Expectation'

        results = sorted(student_data.values(), key=lambda x: x['avg'], reverse=True)

        total = len(results)
        for i, r in enumerate(results, start=1):
            r['position'] = i
            r['out_of_total'] = total
                # ---------- Add stats for the redesigned template ----------
    total_students = len(results)
    class_average = round(
        sum(r['avg'] for r in results) / total_students, 1
    ) if total_students else 0
    top_score = max((r['avg'] for r in results), default=0)

    # Collect all subjects present
    all_subjects = set()
    for r in results:
        for g in r.get('subjects', []):
            all_subjects.add(g.subject.name)
    subject_count = len(all_subjects)

    # Add class_teacher name for the header
    class_teacher_name = None
    try:
        from apps.teachers.models import Teacher
        ct = Teacher.objects.filter(
            school=school,
            current_class=selected_class,
            is_class_teacher=True,
            is_active=True,
        ).select_related('user').first()
        if ct:
            class_teacher_name = ct.user.get_full_name or ct.user.email
    except Exception:
        pass

    return render(request, 'dashboard/class_results.html', {
        'classes': classes,
        'exams': exams,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': total_students,
        'class_average': class_average,
        'top_score': top_score,
        'subject_count': subject_count,
        'class_teacher_name': class_teacher_name,
    })

    return render(request, 'dashboard/class_results.html', {
        'classes': classes,
        'exams': exams,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': len(results),
    })


@login_required
def class_results_pdf(request):
    if request.user.role not in ('teacher', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    school = user.school

    class_id = request.GET.get('class')
    exam_id = request.GET.get('exam')

    try:
        selected_class = ClassLevel.objects.get(id=class_id, school=school)
        selected_exam = Exam.objects.get(id=exam_id, school=school)
    except (ClassLevel.DoesNotExist, Exam.DoesNotExist):
        messages.error(request, 'Invalid class or exam.')
        return redirect('class_results')

    students = Student.objects.filter(
        school=school, class_level=selected_class.name, is_active=True
    )

    grades_qs = Grade.objects.filter(
        exam=selected_exam, student__in=students
    ).select_related('subject', 'student')

    student_data = {}
    for g in grades_qs:
        sid = g.student_id
        if sid not in student_data:
            student_data[sid] = {'student': g.student, 'marks': 0, 'out_of': 0}
        student_data[sid]['marks'] += float(g.marks)
        student_data[sid]['out_of'] += float(g.out_of)

    for sid, data in student_data.items():
        if data['out_of'] > 0:
            data['avg'] = round((data['marks'] / data['out_of']) * 100, 1)
        else:
            data['avg'] = 0
        avg = data['avg']
        if avg >= 80:
            data['cbc'] = 'EE'
        elif avg >= 65:
            data['cbc'] = 'ME'
        elif avg >= 50:
            data['cbc'] = 'AE'
        else:
            data['cbc'] = 'BE'

    results = sorted(student_data.values(), key=lambda x: x['avg'], reverse=True)
    total = len(results)
    for i, r in enumerate(results, start=1):
        r['position'] = i
        r['out_of_total'] = total

    class_teacher = Teacher.objects.filter(
        school=school, current_class=selected_class, is_class_teacher=True,
    ).select_related('user').first()

    html_string = render_to_string('pdf/class_results.html', {
        'school': school,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': total,
        'class_teacher': class_teacher,
        'user': user,
    })

    filename = f'class_results_{selected_class.name}_{selected_exam.name}.pdf'
    return html_to_pdf_response(html_string, filename)


# ==========================================================
# SMART ALERTS DASHBOARD
# ==========================================================

@login_required
def alerts_dashboard(request):
    from apps.notifications.models import Alert

    user = request.user

    if user.role == 'super_admin':
        alerts = Alert.objects.all()
    elif user.school:
        alerts = Alert.objects.filter(school=user.school)
    else:
        alerts = Alert.objects.none()

    severity = request.GET.get('severity', '')
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')

    if severity:
        alerts = alerts.filter(severity=severity)
    if status:
        alerts = alerts.filter(status=status)
    if category:
        alerts = alerts.filter(category=category)

    all_alerts = Alert.objects.filter(school=user.school) if user.school else Alert.objects.all()
    counts = {
        'new': all_alerts.filter(status='new').count(),
        'critical': all_alerts.filter(severity='critical', status='new').count(),
        'high': all_alerts.filter(severity='high', status='new').count(),
        'medium': all_alerts.filter(severity='medium', status='new').count(),
        'low': all_alerts.filter(severity='low', status='new').count(),
    }

    return render(request, 'dashboard/alerts.html', {
        'alerts': alerts.select_related('school', 'resolved_by'),
        'counts': counts,
        'filter_severity': severity,
        'filter_status': status,
        'filter_category': category,
    })


@login_required
def alert_resolve(request, alert_id):
    from apps.notifications.models import Alert

    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    alert = get_object_or_404(Alert, id=alert_id)

    if request.user.role != 'super_admin' and alert.school != request.user.school:
        return redirect('dashboard_home')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        alert.resolve(request.user, notes)
        messages.success(request, f'Alert resolved: {alert.title}')
        return redirect('alerts_dashboard')

    return render(request, 'dashboard/alert_resolve.html', {'alert': alert})


@login_required
def alert_dismiss(request, alert_id):
    from apps.notifications.models import Alert

    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    alert = get_object_or_404(Alert, id=alert_id)

    if request.user.role != 'super_admin' and alert.school != request.user.school:
        return redirect('dashboard_home')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        alert.dismiss(request.user, notes)
        messages.success(request, 'Alert dismissed.')
        return redirect('alerts_dashboard')

    return render(request, 'dashboard/alert_dismiss.html', {'alert': alert})


@login_required
def run_scan(request):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.services.smart_alerts import run_all_detections

    try:
        school = request.user.school if request.user.role != 'super_admin' else None
        count = run_all_detections(school)
        if count:
            messages.success(request, f'Scan complete. {count} new alert(s) found.')
        else:
            messages.info(request, 'Scan complete. No new alerts.')
    except Exception as e:
        messages.error(request, f'Scan failed: {e}')

    return redirect('alerts_dashboard')


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

@login_required
def accountant_transactions(request):
    """School accountant sees all transactions, expenditure, debts, credit."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment, Expenditure
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from datetime import date, timedelta
    from django.db.models import Sum, F

    user = request.user
    school = user.school

    # ---------- Period selection ----------
    period = request.GET.get('period', 'month')
    today = date.today()

    if period == 'month':
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')
    elif period == 'term':
        start_date = today - timedelta(days=90)
        end_date = today
        period_label = 'Last 90 days'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = str(today.year)
    elif period == 'custom':
        try:
            start_date = date.fromisoformat(request.GET.get('start', ''))
            end_date = date.fromisoformat(request.GET.get('end', ''))
        except (ValueError, TypeError):
            start_date = today.replace(day=1)
            end_date = today
        period_label = f'{start_date.strftime("%d %b %Y")} to {end_date.strftime("%d %b %Y")}'
    else:
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')

    # ---------- Fee Collections ----------
    payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date,
    ).select_related('invoice__student')

    total_collected = float(
        payments.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Breakdown by method
    method_breakdown = {}
    for row in payments.values('method').annotate(t=Sum('amount_kes')):
        label = dict(Payment.Method.choices).get(row['method'], row['method'])
        method_breakdown[label] = float(row['t'] or 0)

    # ---------- Expenditure ----------
    expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=start_date,
        spent_on__lte=end_date,
    )

    total_expenditure = float(
        expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Breakdown by category
    category_breakdown = {}
    for row in expenditures.values('category').annotate(t=Sum('amount_kes')):
        label = dict(Expenditure.Category.choices).get(row['category'], row['category'])
        category_breakdown[label] = float(row['t'] or 0)

    # ---------- Debtors ----------
    outstanding_agg = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))

    total_debts = float(outstanding_agg['t'] or 0)

    debt_count = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).values('student_id').distinct().count()

    # ---------- Net Position ----------
    net_position = total_collected - total_expenditure

    # ---------- Previous period comparison ----------
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    prev_payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=prev_start,
        paid_at__date__lte=prev_end,
    )
    prev_collected = float(
        prev_payments.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    prev_expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=prev_start,
        spent_on__lte=prev_end,
    )
    prev_expenditure = float(
        prev_expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Comparison helper
    def delta(curr, prev):
        curr = float(curr or 0)
        prev = float(prev or 0)
        if prev == 0:
            pct = 100 if curr > 0 else 0
            return {
                'pct': pct,
                'abs': curr - prev,
                'direction': 'up' if curr > prev else ('down' if curr < prev else 'flat'),
            }
        pct = round(((curr - prev) / prev) * 100, 1)
        return {
            'pct': pct,
            'abs': curr - prev,
            'direction': 'up' if pct > 0 else ('down' if pct < 0 else 'flat'),
        }

    collected_delta = delta(total_collected, prev_collected)
    expenditure_delta = delta(total_expenditure, prev_expenditure)
    net_delta = delta(net_position, prev_collected - prev_expenditure)

    # ---------- Per-class collection breakdown ----------
    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_student_ids = list(
            Student.objects.filter(
                school=school, class_level=cls.name, is_active=True
            ).values_list('id', flat=True)
        )
        if not class_student_ids:
            continue

        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_student_ids,
                paid_at__date__gte=start_date,
                paid_at__date__lte=end_date,
            ).aggregate(t=Sum('amount_kes'))['t'] or 0
        )

        class_outstanding = float(
            Invoice.objects.filter(
                student_id__in=class_student_ids,
                status__in=['unpaid', 'partial', 'overdue'],
            ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))['t'] or 0
        )

        class_breakdown.append({
            'class_name': cls.name,
            'students': len(class_student_ids),
            'collected': class_collected,
            'outstanding': class_outstanding,
        })

    class_breakdown.sort(key=lambda x: x['collected'], reverse=True)

    # ---------- Recent transactions (for table at bottom) ----------
    recent_payments = payments.select_related('invoice__student').order_by('-paid_at')[:20]

    # ---------- Render ----------
    return render(request, 'dashboard/accountant_transactions.html', {
        'period': period,
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'start_date_iso': start_date.isoformat(),
        'end_date_iso': end_date.isoformat(),

        # Summary
        'total_collected': total_collected,
        'total_expenditure': total_expenditure,
        'total_debts': total_debts,
        'debt_count': debt_count,
        'net_position': net_position,

        # Breakdowns
        'method_breakdown': method_breakdown,
        'category_breakdown': category_breakdown,
        'class_breakdown': class_breakdown,

        # Comparison
        'prev_collected': prev_collected,
        'prev_expenditure': prev_expenditure,
        'prev_start': prev_start,
        'prev_end': prev_end,
        'collected_delta': collected_delta,
        'expenditure_delta': expenditure_delta,
        'net_delta': net_delta,

        # Recent
        'recent_payments': recent_payments,
    })

@login_required
def add_expenditure(request):
    """Accountant adds an expenditure entry."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import Expenditure

    if request.method == 'POST':
        category = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        spent_on = request.POST.get('spent_on') or None
        paid_to = request.POST.get('paid_to', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference = request.POST.get('reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not category:
            errors.append('Category is required.')
        if not description:
            errors.append('Description is required.')
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not spent_on:
            errors.append('Date is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Expenditure.objects.create(
                school=request.user.school,
                category=category,
                description=description,
                amount_kes=amount,
                spent_on=spent_on,
                paid_to=paid_to,
                payment_method=payment_method,
                reference=reference,
                notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'Expenditure of KES {amount:,.2f} recorded.')
            return redirect('accountant_transactions')

    return render(request, 'dashboard/add_expenditure.html', {
        'categories': Expenditure.Category.choices,
    })
    # ==========================================================
# TEST SMS
# ==========================================================

@login_required
def send_test_sms_view(request):
    """Admin page to send a test SMS."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    result = None

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        message = request.POST.get('message', 'Test SMS from School MS').strip()

        if not phone:
            messages.error(request, 'Phone number required.')
        else:
            try:
                from apps.notifications.services.sms import send_sms
                result = send_sms(phone, message)

                if result.get('success'):
                    messages.success(request, f'SMS sent to {phone}. Check your phone.')
                else:
                    messages.error(request, f'Failed: {result.get("message")}')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    return render(request, 'dashboard/test_sms.html', {'result': result})

# ==========================================================
# BULK SMS
# ==========================================================

@login_required
def bulk_sms(request):
    """Send bulk SMS to groups of parents."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.parents.models import Parent
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.finance.models import Invoice
    from apps.notifications.services.sms import send_bulk_sms, normalize_phone

    school = request.user.school
    all_parents = Parent.objects.filter(user__school=school).select_related('user')

    unpaid_student_ids = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).values_list('student_id', flat=True).distinct()

    unpaid_parents = Parent.objects.filter(
        user__school=school, students__id__in=unpaid_student_ids
    ).distinct()

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    def count_with_phones(qs):
        n = 0
        for p in qs:
            phone = p.user.phone or p.phone
            if phone and normalize_phone(phone):
                n += 1
        return n

    counts = {
        'all': count_with_phones(all_parents),
        'unpaid': count_with_phones(unpaid_parents),
    }

    result = None
    if request.method == 'POST':
        group = request.POST.get('group', 'all')
        class_id = request.POST.get('class_id')
        custom_numbers = request.POST.get('custom_numbers', '').strip()
        message = request.POST.get('message', '').strip()

        if not message:
            messages.error(request, 'Message cannot be empty.')
        else:
            phones = []

            if group == 'custom':
                raw = custom_numbers.replace('\n', ',').split(',')
                for num in raw:
                    num = num.strip()
                    if num and normalize_phone(num):
                        phones.append(num)
            elif group == 'unpaid':
                for p in unpaid_parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)
            elif group == 'class' and class_id:
                student_ids = Student.objects.filter(
                    school=school, class_level=class_id, is_active=True
                ).values_list('id', flat=True)
                parents = Parent.objects.filter(
                    user__school=school, students__id__in=student_ids
                ).distinct()
                for p in parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)
            else:
                for p in all_parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)

            phones = list(set(phones))

            if not phones:
                messages.error(request, 'No valid recipients with phone numbers.')
            else:
                try:
                    result = send_bulk_sms(phones, message)
                    if result.get('success'):
                        messages.success(request, f'Bulk SMS sent to {len(phones)} recipients.')
                    else:
                        messages.error(request, f'Failed: {result.get("message")}')
                except Exception as e:
                    messages.error(request, f'Error: {e}')

    return render(request, 'dashboard/bulk_sms.html', {
        'counts': counts,
        'classes': classes,
        'result': result,
    })
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

@login_required
def messages_inbox(request):
    """Each user sees messages sent to them."""
    from apps.notifications.models import MessageRecipient

    qs = MessageRecipient.objects.filter(
        recipient=request.user, is_archived=False
    ).select_related('message', 'message__sender', 'message__school').order_by('-message__created_at')

    unread_count = qs.filter(is_read=False).count()

    return render(request, 'dashboard/messages_inbox.html', {
        'messages': qs,
        'unread_count': unread_count,
    })


@login_required
def message_detail(request, recipient_id):
    """View a single message and mark it as read."""
    from apps.notifications.models import MessageRecipient

    msg_recipient = get_object_or_404(
        MessageRecipient, id=recipient_id, recipient=request.user
    )
    msg_recipient.mark_read()

    return render(request, 'dashboard/message_detail.html', {
        'recipient': msg_recipient,
        'message': msg_recipient.message,
    })
    

@login_required
def message_archive(request, recipient_id):
    """Archive a message (hide from inbox)."""
    from apps.notifications.models import MessageRecipient

    msg_recipient = get_object_or_404(
        MessageRecipient, id=recipient_id, recipient=request.user
    )
    msg_recipient.is_archived = True
    msg_recipient.save()
    messages.success(request, 'Message archived.')
    return redirect('messages_inbox')


@login_required
def compose_message(request):
    """School Admin composes a new message."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message, MessageRecipient
    from apps.accounts.models import User

    school = request.user.school

    # Count recipients for each group
    teachers = User.objects.filter(school=school, role='teacher', is_active=True)
    staff_users = User.objects.filter(school=school, role='accountant', is_active=True)
    class_teachers = User.objects.filter(
        school=school, role='teacher', is_active=True,
        teacher_profile__is_class_teacher=True
    )

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        priority = request.POST.get('priority', 'normal')
        category = request.POST.get('category', 'general')
        recipient_group = request.POST.get('recipient_group', 'teachers')
        specific_id = request.POST.get('specific_recipient', '').strip()

        errors = []
        if not subject:
            errors.append('Subject is required.')
        if not body:
            errors.append('Message body is required.')

        # Determine recipients
        recipients_qs = User.objects.none()

        if recipient_group == 'teachers':
            recipients_qs = teachers
        elif recipient_group == 'staff':
            recipients_qs = staff_users
        elif recipient_group == 'class_teachers':
            recipients_qs = class_teachers
        elif recipient_group == 'all':
            recipients_qs = User.objects.filter(
                school=school,
                role__in=['teacher', 'accountant'],
                is_active=True
            )
        elif recipient_group == 'specific' and specific_id:
            recipients_qs = User.objects.filter(
                id=specific_id, school=school, is_active=True
            )

        if not recipients_qs.exists():
            errors.append('No recipients found for the selected group.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # Create the message
            msg = Message.objects.create(
                school=school,
                sender=request.user,
                subject=subject,
                body=body,
                priority=priority,
                category=category,
            )

            # Create recipient rows
            recipient_count = 0
            for r in recipients_qs:
                MessageRecipient.objects.create(message=msg, recipient=r)
                recipient_count += 1

                # Also create in-app notification
                try:
                    from apps.notifications.models import Notification
                    Notification.objects.create(
                        recipient=r,
                        channel='in_app',
                        title=f'New message: {subject}',
                        message=body[:200],
                        is_read=False,
                    )
                except Exception:
                    pass

            messages.success(request, f'Message sent to {recipient_count} recipient(s).')
            return redirect('messages_sent')

    # Counts for display
    counts = {
        'teachers': teachers.count(),
        'staff': staff_users.count(),
        'class_teachers': class_teachers.count(),
        'all': User.objects.filter(
            school=school,
            role__in=['teacher', 'accountant'],
            is_active=True
        ).count(),
    }

    all_recipients = User.objects.filter(
        school=school,
        role__in=['teacher', 'accountant'],
        is_active=True,
    ).order_by('first_name', 'last_name')

    return render(request, 'dashboard/messages_compose.html', {
        'counts': counts,
        'all_recipients': all_recipients,
    })


@login_required
def messages_sent(request):
    """School Admin sees their sent messages."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message

    sent = Message.objects.filter(
        sender=request.user
    ).prefetch_related('recipients').order_by('-created_at')

    return render(request, 'dashboard/messages_sent.html', {
        'messages': sent,
    })


@login_required
def message_delete(request, message_id):
    """Sender can delete a message."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message

    msg = get_object_or_404(Message, id=message_id, sender=request.user)
    msg.delete()
    messages.success(request, 'Message deleted.')
    return redirect('messages_sent')

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

@login_required
@login_required
def accountant_students(request):
    """List all students with their fee balances for the accountant."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel
    from django.db.models import Sum, Q

    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school

    # Filters
    search = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '')
    status_filter = request.GET.get('status', '').strip()

    # ---------- All students ----------
    students_qs = Student.objects.filter(
        school=school, is_active=True
    ).order_by('class_level', 'first_name', 'last_name')

    if search:
        students_qs = students_qs.filter(
            Q(first_name__icontains=search) |
            Q(middle_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search) |
            Q(upi__icontains=search)
        )

    if class_id:
        try:
            cls = ClassLevel.objects.get(id=class_id, school=school)
            students_qs = students_qs.filter(class_level=cls.name)
        except ClassLevel.DoesNotExist:
            pass

    # ---------- Batch invoice totals (much faster than per-student loop) ----------
    student_ids = list(students_qs.values_list('id', flat=True))

    invoice_totals = (
        Invoice.objects
        .filter(student_id__in=student_ids)
        .values('student_id')
        .annotate(
            inv=Sum('amount_due'),
            pd=Sum('amount_paid'),
        )
    )
    invoice_map = {
        row['student_id']: {
            'invoiced': float(row['inv'] or 0),
            'paid': float(row['pd'] or 0),
        }
        for row in invoice_totals
    }

    # ---------- Build student rows ----------
    student_list = []
    grand_invoiced = 0
    grand_paid = 0

    for s in students_qs:
        totals = invoice_map.get(s.id, {'invoiced': 0, 'paid': 0})
        total_invoiced = totals['invoiced']
        total_paid = totals['paid']
        balance = total_invoiced - total_paid

        # Determine status
        if total_invoiced == 0:
            status = 'none'
        elif balance <= 0:
            status = 'paid'
        elif total_paid > 0:
            status = 'partial'
        else:
            status = 'unpaid'

        # Apply status filter
        if status_filter and status != status_filter:
            continue

        student_list.append({
            'student': s,
            'invoiced': total_invoiced,
            'paid': total_paid,
            'balance': balance,
            'status': status,
        })

        grand_invoiced += total_invoiced
        grand_paid += total_paid

    grand_balance = grand_invoiced - grand_paid

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    return render(request, 'dashboard/accountant_students.html', {
        'students_data': student_list,
        'total_students': len(student_list),
        'grand_invoiced': grand_invoiced,
        'grand_paid': grand_paid,
        'grand_balance': grand_balance,
        'classes': classes,
        'search': search,
        'class_id': class_id,
        'status_filter': status_filter,
    })
    # ==========================================================
# ACCOUNTANT — CLASS FEE STATEMENT
# ==========================================================

@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def class_fee_statement(request):
    """Shows fee summary for one class + per-student breakdown."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # ---------- Class selector ----------
    class_id = request.GET.get('class')
    if not class_id and classes.exists():
        class_id = classes.first().id

    selected_class = None
    if class_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
        except ClassLevel.DoesNotExist:
            pass

    # ---------- Search + Status filter ----------
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    # ---------- Students + invoices ----------
    students_data = []
    class_invoiced = 0
    class_paid = 0
    counts = {'paid': 0, 'partial': 0, 'unpaid': 0, 'overdue': 0, 'none': 0}

    if selected_class:
        students_qs = Student.objects.filter(
            school=school,
            class_level=selected_class.name,
            is_active=True,
        ).order_by('first_name', 'last_name')

        if search:
            students_qs = students_qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(middle_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(admission_number__icontains=search)
            )

        for s in students_qs:
            invoices = Invoice.objects.filter(student=s)
            total_invoiced = sum(i.amount_due for i in invoices) or 0
            total_paid = sum(i.amount_paid for i in invoices) or 0
            balance = total_invoiced - total_paid

            if total_invoiced == 0:
                status = 'none'
            elif balance <= 0:
                status = 'paid'
            elif any(i.status == 'overdue' for i in invoices):
                status = 'overdue'
            elif total_paid > 0:
                status = 'partial'
            else:
                status = 'unpaid'

            counts[status] = counts.get(status, 0) + 1

            # Apply status filter
            if status_filter and status != status_filter:
                continue

            students_data.append({
                'student': s,
                'invoiced': total_invoiced,
                'paid': total_paid,
                'balance': balance,
                'status': status,
                'invoice_count': invoices.count(),
            })

            class_invoiced += total_invoiced
            class_paid += total_paid

    class_balance = class_invoiced - class_paid

    return render(request, 'dashboard/class_fee_statement.html', {
        'classes': classes,
        'selected_class': selected_class,
        'students_data': students_data,
        'total_students': len(students_data),
        'class_invoiced': class_invoiced,
        'class_paid': class_paid,
        'class_balance': class_balance,
        'counts': counts,
        'search': search,
        'status_filter': status_filter,
    })


@login_required
@role_required('accountant', 'school_admin')
def class_fee_statement_pdf(request, class_id):
    """Generate PDF of class fee statement (A4 landscape)."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school

    try:
        selected_class = ClassLevel.objects.get(id=class_id, school=school)
    except ClassLevel.DoesNotExist:
        messages.error(request, 'Class not found.')
        return redirect('class_fee_statement')

    students = Student.objects.filter(
        school=school,
        class_level=selected_class.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    students_data = []
    class_invoiced = 0
    class_paid = 0

    for s in students:
        invoices = Invoice.objects.filter(student=s)
        total_invoiced = sum(i.amount_due for i in invoices) or 0
        total_paid = sum(i.amount_paid for i in invoices) or 0
        balance = total_invoiced - total_paid

        if total_invoiced == 0:
            status = 'none'
        elif balance <= 0:
            status = 'paid'
        elif total_paid > 0:
            status = 'partial'
        else:
            status = 'unpaid'

        students_data.append({
            'student': s,
            'invoiced': total_invoiced,
            'paid': total_paid,
            'balance': balance,
            'status': status,
        })

        class_invoiced += total_invoiced
        class_paid += total_paid

    class_balance = class_invoiced - class_paid

    html_string = render_to_string('pdf/class_fee_statement.html', {
        'school': school,
        'selected_class': selected_class,
        'students_data': students_data,
        'total_students': len(students_data),
        'class_invoiced': class_invoiced,
        'class_paid': class_paid,
        'class_balance': class_balance,
        'printed_by': request.user,
    })

    filename = f'class_statement_{selected_class.name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)
# ==========================================================
# EXPENDITURE MANAGEMENT
# ==========================================================

@login_required
def expenditure_list(request):
    """List all expenditures with filters, pagination, and category summary."""
    from apps.finance.models import Expenditure
    from django.db.models import Sum, Count
    from django.core.paginator import Paginator
    from collections import defaultdict
    from django.utils.dateparse import parse_date

    school = request.user.school

    base_qs = Expenditure.objects.filter(
        school=school
    ).select_related('recorded_by').order_by('-spent_on', '-created_at')

    # ---------- Filters ----------
    category = request.GET.get('category', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    search = request.GET.get('q', '').strip()

    qs = base_qs

    if category:
        qs = qs.filter(category=category)

    if date_from:
        d = parse_date(date_from)
        if d:
            qs = qs.filter(spent_on__gte=d)

    if date_to:
        d = parse_date(date_to)
        if d:
            qs = qs.filter(spent_on__lte=d)

    if search:
        qs = qs.filter(
            models.Q(description__icontains=search) |
            models.Q(paid_to__icontains=search) |
            models.Q(reference__icontains=search)
        )

    # ---------- Aggregate ----------
    agg = qs.aggregate(
        total=Sum('amount_kes'),
        count=Count('id'),
    )
    total = float(agg['total'] or 0)
    count = agg['count'] or 0

    # ---------- Category breakdown ----------
    category_totals = (
        qs.values('category')
        .annotate(subtotal=Sum('amount_kes'), cnt=Count('id'))
        .order_by('-subtotal')
    )
    category_labels = dict(Expenditure.Category.choices)
    category_summary = [
        {
            'code': row['category'],
            'label': category_labels.get(row['category'], row['category']),
            'total': float(row['subtotal'] or 0),
            'count': row['cnt'],
        }
        for row in category_totals
    ]

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/expenditure_list.html', {
        'expenditures': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': total,
        'count': count,
        'categories': Expenditure.Category.choices,
        'category_summary': category_summary,
        'category_filter': category,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    })

@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def expenditure_add(request):
    """Add new expenditure."""
    from apps.finance.models import Expenditure

    if request.method == 'POST':
        category = request.POST.get('category', '')
        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        spent_on = request.POST.get('spent_on') or None
        paid_to = request.POST.get('paid_to', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference = request.POST.get('reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not category: errors.append('Category is required.')
        if not description: errors.append('Description is required.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not spent_on: errors.append('Date is required.')

        if errors:
            for e in errors: messages.error(request, e)
        else:
            Expenditure.objects.create(
                school=request.user.school,
                category=category, description=description,
                amount_kes=amount, spent_on=spent_on,
                paid_to=paid_to, payment_method=payment_method,
                reference=reference, notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'✅ Expenditure of KES {amount:,.2f} recorded.')
            return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices,
        'action': 'add',
    })


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def expenditure_edit(request, expenditure_id):
    """Edit existing expenditure."""
    from apps.finance.models import Expenditure

    exp = get_object_or_404(Expenditure, id=expenditure_id, school=request.user.school)

    if request.method == 'POST':
        exp.category = request.POST.get('category', exp.category)
        exp.description = request.POST.get('description', exp.description).strip()
        exp.spent_on = request.POST.get('spent_on') or exp.spent_on
        exp.paid_to = request.POST.get('paid_to', '').strip()
        exp.payment_method = request.POST.get('payment_method', exp.payment_method)
        exp.reference = request.POST.get('reference', '').strip()
        exp.notes = request.POST.get('notes', '').strip()

        try:
            exp.amount_kes = float(request.POST.get('amount_kes', exp.amount_kes))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('expenditure_edit', expenditure_id=exp.id)

        exp.save()
        messages.success(request, '✅ Expenditure updated.')
        return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices,
        'expenditure': exp,
        'action': 'edit',
    })


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def expenditure_delete(request, expenditure_id):
    """Delete expenditure."""
    from apps.finance.models import Expenditure

    exp = get_object_or_404(Expenditure, id=expenditure_id, school=request.user.school)

    if request.method == 'POST':
        desc = exp.description
        exp.delete()
        messages.success(request, f'🗑️ Expenditure "{desc}" deleted.')
        return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_delete.html', {'expenditure': exp})


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def expenditure_pdf(request):
    """Generate PDF of expenditures with filters."""
    from apps.finance.models import Expenditure
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school
    qs = Expenditure.objects.filter(school=school).order_by('-spent_on')

    # Apply same filters
    category = request.GET.get('category', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if category: qs = qs.filter(category=category)
    if date_from:
        try: qs = qs.filter(spent_on__gte=date_from)
        except: pass
    if date_to:
        try: qs = qs.filter(spent_on__lte=date_to)
        except: pass

    total = sum(e.amount_kes for e in qs)

    # Group by category for summary
    category_totals = {}
    for e in qs:
        cat = e.get_category_display()
        category_totals[cat] = category_totals.get(cat, 0) + float(e.amount_kes)

    html_string = render_to_string('pdf/expenditure_statement.html', {
        'school': school,
        'expenditures': qs,
        'total': total,
        'count': qs.count(),
        'category_totals': category_totals,
        'category_filter': category,
        'date_from': date_from,
        'date_to': date_to,
        'printed_by': request.user,
    })

    filename = 'expenditure_statement.pdf'
    return html_to_pdf_response(html_string, filename)
# ==========================================================
# FEE STRUCTURE MANAGEMENT
# ==========================================================

@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def fee_structure_list(request):
    """List all fee structures with filters and summary."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel
    from django.db.models import Sum
    from collections import defaultdict

    school = request.user.school
    qs = FeeStructure.objects.filter(school=school).order_by('-created_at')

    # ---------- Filters ----------
    class_filter = request.GET.get('class', '').strip()
    term_filter = request.GET.get('term', '').strip()
    search = request.GET.get('q', '').strip()

    if class_filter:
        qs = qs.filter(class_level=class_filter)
    if term_filter:
        qs = qs.filter(name__startswith=f"{term_filter} —")
    if search:
        qs = qs.filter(name__icontains=search)

    # ---------- Summary ----------
    total_value = qs.aggregate(t=Sum('amount_kes'))['t'] or 0

    # ---------- Distinct classes used ----------
    all_school_fs = FeeStructure.objects.filter(school=school)
    used_classes = sorted(set(
        all_school_fs.values_list('class_level', flat=True)
    ))

    # ---------- Term choices ----------
    terms = set()
    for name in all_school_fs.values_list('name', flat=True):
        if ' — ' in name:
            terms.add(name.split(' — ', 1)[0])
        else:
            terms.add(name)
    term_choices = sorted(terms)

    # ---------- Group by term for display ----------
    grouped = defaultdict(list)
    for fs in qs:
        if ' — ' in fs.name:
            term = fs.name.split(' — ', 1)[0]
        else:
            term = 'Uncategorized'
        grouped[term].append(fs)

    # Sort terms and get ordered groups
    grouped_list = sorted(
        grouped.items(),
        key=lambda x: x[0],
        reverse=True
    )

    return render(request, 'dashboard/fee_structure_list.html', {
        'fee_structures': qs,
        'count': qs.count(),
        'total_value': total_value,
        'used_classes': used_classes,
        'term_choices': term_choices,
        'class_filter': class_filter,
        'term_filter': term_filter,
        'search': search,
        'grouped_list': grouped_list,
        'all_classes': ClassLevel.objects.filter(school=school).order_by('order', 'name'),
    })

@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def fee_structure_add(request):
    """Create a new fee structure."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        class_level = request.POST.get('class_level', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None

        errors = []
        if not name: errors.append('Name is required.')
        if not class_level: errors.append('Class is required.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not due_date: errors.append('Due date is required.')

        if errors:
            for e in errors: messages.error(request, e)
            return render(request, 'dashboard/fee_structure_form.html', {
                'classes': classes,
                'action': 'add',
                'form_data': request.POST,
            })

        FeeStructure.objects.create(
            school=school,
            name=name,
            class_level=class_level,
            amount_kes=amount,
            due_date=due_date,
        )
        messages.success(request, f'✅ Fee structure "{name}" created for {class_level}.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {
        'classes': classes,
        'action': 'add',
    })


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def fee_structure_edit(request, fee_id):
    """Edit an existing fee structure."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    fs = get_object_or_404(FeeStructure, id=fee_id, school=school)
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        fs.name = request.POST.get('name', fs.name).strip()
        fs.class_level = request.POST.get('class_level', fs.class_level).strip()
        fs.due_date = request.POST.get('due_date') or fs.due_date

        try:
            fs.amount_kes = float(request.POST.get('amount_kes', fs.amount_kes))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('fee_structure_edit', fee_id=fs.id)

        fs.save()
        messages.success(request, f'✅ Fee structure "{fs.name}" updated.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {
        'classes': classes,
        'fee_structure': fs,
        'action': 'edit',
    })


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def fee_structure_delete(request, fee_id):
    """Delete a fee structure."""
    from apps.finance.models import FeeStructure

    fs = get_object_or_404(FeeStructure, id=fee_id, school=request.user.school)

    if request.method == 'POST':
        name = fs.name
        fs.delete()
        messages.success(request, f'🗑️ Fee structure "{name}" deleted.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_delete.html', {'fee_structure': fs})


@login_required
@role_required('accountant', 'school_admin', 'super_admin')
def fee_structure_bulk(request):
    """
    Bulk-draft fee structures across ALL classes.

    The user enters a fee name, amount, and due date, and selects which classes
    should receive this fee. All selected classes get a FeeStructure created
    with the same amount.
    """
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None
        selected_class_ids = request.POST.getlist('classes')  # list of class IDs
        skip_existing = request.POST.get('skip_existing') == 'on'

        errors = []
        if not name: errors.append('Fee name is required.')
        if not selected_class_ids: errors.append('Select at least one class.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not due_date: errors.append('Due date is required.')

        if errors:
            for e in errors: messages.error(request, e)
            return render(request, 'dashboard/fee_structure_bulk.html', {
                'classes': classes,
                'form_data': request.POST,
            })

        created = 0
        skipped = 0

        for class_id in selected_class_ids:
            try:
                cls = ClassLevel.objects.get(id=class_id, school=school)
            except ClassLevel.DoesNotExist:
                continue

            # Check for existing fee with same name + class
            exists = FeeStructure.objects.filter(
                school=school,
                name=name,
                class_level=cls.name,
            ).exists()

            if exists and skip_existing:
                skipped += 1
                continue

            FeeStructure.objects.create(
                school=school,
                name=name,
                class_level=cls.name,
                amount_kes=amount,
                due_date=due_date,
            )
            created += 1

        messages.success(
            request,
            f'✅ Created {created} fee structure{{created|pluralize}}'
            + (f' · Skipped {skipped} duplicate{{skipped|pluralize}}' if skipped else '')
            + '.'
        )
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_bulk.html', {
        'classes': classes,
    })
    # ==========================================================
# FEE STRUCTURE MATRIX EDITOR
# ==========================================================

@login_required
def fee_structure_matrix(request):
    """Bulk draft page — matrix editor for fee items × classes."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    import json
    from django.utils import timezone
    from datetime import timedelta
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    classes_json = json.dumps([
        {'id': c.id, 'name': c.name} for c in classes
    ])

    # Default term name suggestion
    today = timezone.now().date()
    year = today.year
    default_term_name = f"Term {((today.month - 1) // 4) + 1} {year}"

    # Default due date = 30 days from now
    default_due_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')

    return render(request, 'dashboard/fee_structure_matrix.html', {
        'classes_json': classes_json,
        'default_term_name': default_term_name,
        'default_due_date': default_due_date,
    })


@login_required
def fee_structure_matrix_save(request):
    """Receives the matrix JSON and creates FeeStructure rows."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    import json
    from django.db import transaction
    from datetime import datetime
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    term_name = (payload.get('term_name') or '').strip()
    due_date_str = (payload.get('due_date') or '').strip()
    rows = payload.get('rows') or []

    if not term_name:
        return JsonResponse({'success': False, 'error': 'Term name is required'}, status=400)

    if not due_date_str:
        return JsonResponse({'success': False, 'error': 'Due date is required'}, status=400)

    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)

    if not rows:
        return JsonResponse({'success': False, 'error': 'No fee items provided'}, status=400)

    school = request.user.school

    # Validate class IDs belong to this school
    valid_class_ids = set(
        ClassLevel.objects.filter(school=school).values_list('id', flat=True)
    )

    created = 0
    updated = 0

    try:
        with transaction.atomic():
            for row in rows:
                item_name = (row.get('name') or '').strip()
                if not item_name:
                    continue

                amounts = row.get('amounts') or {}
                full_name = f"{term_name} — {item_name}"

                for cls_id_str, amount in amounts.items():
                    try:
                        cls_id = int(cls_id_str)
                        amount_val = float(amount) if amount not in (None, '') else 0
                    except (ValueError, TypeError):
                        continue

                    if amount_val <= 0:
                        continue
                    if cls_id not in valid_class_ids:
                        continue

                    cls = ClassLevel.objects.get(id=cls_id)

                    obj, was_created = FeeStructure.objects.update_or_create(
                        school=school,
                        name=full_name,
                        class_level=cls.name,
                        defaults={
                            'amount_kes': amount_val,
                            'due_date': due_date,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({
        'success': True,
        'created': created,
        'updated': updated,
        'message': f'{created} created, {updated} updated.',
    })
    # ==========================================================
# FEE STRUCTURE PDF
# ==========================================================

@login_required
def fee_structure_class_pdf(request, class_name):
    """Print/download the fee structure for ONE class as A4 portrait PDF."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from django.utils import timezone
    from urllib.parse import unquote
    from apps.finance.models import FeeStructure
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from urllib.parse import unquote
    class_name = unquote(class_name).strip()

    school = request.user.school
    class_name = unquote(class_name).strip()
    term_filter = request.GET.get('term', '').strip()

    # Fetch fee structures for THIS class only
    qs = FeeStructure.objects.filter(
        school=school,
        class_level=class_name,
    ).order_by('name')

    if term_filter:
        qs = qs.filter(name__startswith=f"{term_filter} —")

    if not qs.exists():
        return HttpResponse(
            f'<h1>No fee structure found for {class_name}</h1>'
            '<p>Draft fees for this class first.</p>',
            status=404
        )

    # Group by term prefix
    terms = set()
    items = []  # list of (item_name, amount)
    due_date = None
    total = 0

    for fs in qs:
        if ' — ' in fs.name:
            term_part, item_part = fs.name.split(' — ', 1)
            terms.add(term_part)
        else:
            term_part = fs.name
            item_part = fs.name
            terms.add(term_part)

        items.append((item_part, float(fs.amount_kes)))
        total += float(fs.amount_kes)
        if due_date is None:
            due_date = fs.due_date

    term_name = term_filter if term_filter else (sorted(terms)[-1] if terms else 'Fee Structure')

    # Logo path (Option A — file path)
    school_logo_path = ''
    if school.logo and hasattr(school.logo, 'path'):
        try:
            school_logo_path = school.logo.path
        except (ValueError, NotImplementedError):
            school_logo_path = ''

    html_string = render_to_string('pdf/fee_structure.html', {
        'school': school,
        'school_logo_path': school_logo_path,
        'term_name': term_name,
        'due_date': due_date,
        'class_name': class_name,
        # Single-class mode: one column, one item per row
        'classes': [{'name': class_name}],
        'rows': [
            {'name': name, 'amounts': [amount], 'total': amount}
            for name, amount in sorted(items)
        ],
        'column_totals': [total],
        'grand_total': total,
        'generated_at': timezone.now(),
        'generated_by': request.user,
    })

    safe_class = class_name.replace(' ', '_').replace('/', '-')
    filename = f'fee_structure_{safe_class}_{term_name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)
# ==========================================================
# CLASS TEACHER — Sub-views (stubs, filled in later messages)
# ==========================================================

# ==========================================================
# CLASS TEACHER — Attendance marking
# ==========================================================

# ==========================================================
# CLASS TEACHER — Grades entry + rankings
# ==========================================================

@login_required
@class_teacher_only
def class_teacher_grades(request):
    """Excel-style grades entry for the class teacher's class."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade
    from apps.academics.models import Subject
    from django.utils import timezone
    import json

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        messages.error(request, 'No teacher profile linked to your account.')
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    exams = Exam.objects.filter(school=user.school).order_by('-year', '-id')

    # ---------- POST: Save grades ----------
    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        payload_str = request.POST.get('payload', '[]')
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            messages.error(request, 'Exam not found.')
            return redirect('class_teacher_grades')

        try:
            rows = json.loads(payload_str)
        except (ValueError, TypeError):
            rows = []

        saved = 0
        for row in rows:
            sid = row.get('student_id')
            sub_id = row.get('subject_id')
            marks = row.get('marks')
            if not (sid and sub_id):
                continue
            try:
                marks_val = float(marks)
            except (ValueError, TypeError):
                continue
            if marks_val < 0 or marks_val > 100:
                continue

            Grade.objects.update_or_create(
                exam=exam,
                student_id=sid,
                subject_id=sub_id,
                defaults={'marks': marks_val, 'out_of': 100},
            )
            saved += 1

        messages.success(request, f'✅ {saved} grades saved for {exam.name}.')
        return redirect(f"{reverse('class_teacher_grades')}?exam={exam.id}")

    # ---------- GET: Load grid ----------
    exam_id = request.GET.get('exam')
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            exam = None

    # Students in class
    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    student_ids = list(students.values_list('id', flat=True))

    # Subjects (all school subjects — teacher filters on the UI)
    subjects = Subject.objects.filter(school=user.school).order_by('name')
    subjects_json = json.dumps([{'id': s.id, 'name': s.name} for s in subjects])

    # Existing marks for this exam
    existing_marks = {}
    if exam:
        grades = Grade.objects.filter(
            exam=exam, student_id__in=student_ids
        ).values_list('student_id', 'subject_id', 'marks')
        for sid, sub_id, marks in grades:
            existing_marks.setdefault(str(sid), {})[str(sub_id)] = float(marks)

    return render(request, 'dashboard/class_teacher_grades.html', {
        'teacher': teacher,
        'cls': cls,
        'exams': exams,
        'exam': exam,
        'students': students,
        'subjects': subjects,
        'subjects_json': subjects_json,
        'existing_marks_json': json.dumps(existing_marks),
        'current_year': timezone.now().year,
    })


@login_required
@class_teacher_only
def class_teacher_new_exam(request):
    """Create a new exam quickly from grades page."""
    if request.method != 'POST':
        return redirect('class_teacher_grades')

    from apps.grades.models import Exam
    from django.utils import timezone

    name = request.POST.get('name', '').strip()
    term = request.POST.get('term', 'Term 1').strip()
    year = request.POST.get('year') or timezone.now().year

    if not name:
        messages.error(request, 'Exam name is required.')
        return redirect('class_teacher_grades')

    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year

    exam = Exam.objects.create(
        school=request.user.school,
        name=name,
        term=term,
        year=year,
    )
    messages.success(request, f'✅ Exam "{exam.name}" created.')
    return redirect(f"{reverse('class_teacher_grades')}?exam={exam.id}")


@login_required
@class_teacher_only
def class_teacher_rankings(request):
    """Rankings table for the class, per exam."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    exams = Exam.objects.filter(school=user.school).order_by('-year', '-id')

    exam_id = request.GET.get('exam')
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            pass
    if not exam and exams.exists():
        exam = exams.first()

    subjects = []
    rankings = []

    if exam:
        students = Student.objects.filter(
            school=user.school, class_level=cls.name, is_active=True,
        ).order_by('first_name', 'last_name')
        student_ids = list(students.values_list('id', flat=True))

        grades = Grade.objects.filter(
            exam=exam, student_id__in=student_ids
        ).select_related('subject')

        # Subjects present
        sub_map = {}
        for g in grades:
            sub_map[g.subject_id] = g.subject
        subjects = sorted(sub_map.values(), key=lambda s: s.name)

        # Marks per student
        by_student = {}
        for g in grades:
            by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

        # Build rankings
        rows = []
        for s in students:
            s_marks = by_student.get(s.id, {})
            marks_list = [s_marks.get(sub.id) for sub in subjects]
            total = sum(m for m in marks_list if m is not None)
            avg = round(total / len(subjects), 1) if subjects else 0
            rows.append({
                'student': s,
                'marks': marks_list,
                'total': total,
                'average': avg,
            })

        # Sort by average desc, assign rank
        rows.sort(key=lambda r: r['average'], reverse=True)
        prev_avg = None
        rank = 0
        for i, r in enumerate(rows, start=1):
            if r['average'] != prev_avg:
                rank = i
                prev_avg = r['average']
            r['rank'] = rank
        rankings = rows

    return render(request, 'dashboard/class_teacher_rankings.html', {
        'teacher': teacher,
        'cls': cls,
        'exams': exams,
        'exam': exam,
        'subjects': subjects,
        'rankings': rankings,
    })


@login_required
@class_teacher_only
def class_teacher_rankings_download(request):
    """Download rankings as CSV."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade
    from django.http import HttpResponse
    import csv

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    exam_id = request.GET.get('exam')

    try:
        exam = Exam.objects.get(id=exam_id, school=user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        messages.error(request, 'Select an exam first.')
        return redirect('class_teacher_rankings')

    students = Student.objects.filter(
        school=user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')
    student_ids = list(students.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).select_related('subject')

    sub_map = {}
    for g in grades:
        sub_map[g.subject_id] = g.subject
    subjects = sorted(sub_map.values(), key=lambda s: s.name)

    by_student = {}
    for g in grades:
        by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

    rows = []
    for s in students:
        s_marks = by_student.get(s.id, {})
        marks_list = [s_marks.get(sub.id) for sub in subjects]
        total = sum(m for m in marks_list if m is not None)
        avg = round(total / len(subjects), 1) if subjects else 0
        rows.append({
            'student': s,
            'marks': marks_list,
            'total': total,
            'average': avg,
        })

    rows.sort(key=lambda r: r['average'], reverse=True)
    prev_avg = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['average'] != prev_avg:
            rank = i
            prev_avg = r['average']
        r['rank'] = rank

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="rankings_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.csv"'
    )

    writer = csv.writer(response)
    header = ['Rank', 'Admission No', 'Student Name']
    header += [s.name for s in subjects]
    header += ['Total', 'Average %']
    writer.writerow(header)

    for r in rows:
        row = [r['rank'], r['student'].admission_number, r['student'].full_name]
        row += ['' if m is None else m for m in r['marks']]
        row += [r['total'], f"{r['average']}%"]
        writer.writerow(row)

    return response


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

@login_required
def admin_alerts_list(request):
    """List all alerts for the school admin."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Alert

    school = request.user.school
    qs = Alert.objects.filter(school=school).order_by('-created_at')

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter in ('new', 'reviewing', 'resolved', 'dismissed'):
        qs = qs.filter(status=status_filter)
    else:
        # Default: show unresolved
        qs = qs.filter(status__in=['new', 'reviewing'])

    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        qs = qs.filter(category=category_filter)

    # Counts
    all_alerts = Alert.objects.filter(school=school)
    counts = {
        'new': all_alerts.filter(status='new').count(),
        'reviewing': all_alerts.filter(status='reviewing').count(),
        'resolved': all_alerts.filter(status='resolved').count(),
        'dismissed': all_alerts.filter(status='dismissed').count(),
        'all': all_alerts.count(),
    }

    return render(request, 'dashboard/admin_alerts_list.html', {
        'alerts': qs[:200],
        'status_filter': status_filter or 'unresolved',
        'category_filter': category_filter,
        'counts': counts,
    })


@login_required
def admin_alert_resolve(request, alert_id):
    """Resolve or dismiss an alert."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Alert

    alert = get_object_or_404(Alert, id=alert_id, school=request.user.school)

    if request.method == 'POST':
        action = request.POST.get('action', 'resolve')
        notes = request.POST.get('notes', '').strip()

        if action == 'dismiss':
            alert.dismiss(request.user, notes)
            messages.success(request, 'Alert dismissed.')
        else:
            alert.resolve(request.user, notes)
            messages.success(request, 'Alert resolved.')

    return redirect('admin_alerts_list')
# ==========================================================
# CLASS TEACHER — Bulk output (results sheet, report cards)
# ==========================================================


def _ct_build_rankings(exam, cls, students, subjects):
    """Build the ranking rows used by results sheet + rankings page."""
    from apps.grades.models import Grade
    student_ids = list(students.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).select_related('subject')

    sub_map = {}
    for g in grades:
        sub_map[g.subject_id] = g.subject
    subjects = sorted(sub_map.values(), key=lambda s: s.name)

    by_student = {}
    for g in grades:
        by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

    rows = []
    for s in students:
        s_marks = by_student.get(s.id, {})
        marks_list = [s_marks.get(sub.id) for sub in subjects]
        total = sum(m for m in marks_list if m is not None)
        avg = round(total / len(subjects), 1) if subjects else 0

        def cbc(p):
            if p >= 80: return 'EE'
            if p >= 65: return 'ME'
            if p >= 50: return 'AE'
            return 'BE'

        rows.append({
            'student': s,
            'marks': marks_list,
            'total': total,
            'average': avg,
            'grade': cbc(avg),
        })

    rows.sort(key=lambda r: r['average'], reverse=True)
    prev_avg = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['average'] != prev_avg:
            rank = i
            prev_avg = r['average']
        r['rank'] = rank

    return rows, subjects


@login_required
@class_teacher_only
def class_teacher_results_sheet_pdf(request):
    """Printable A4 landscape class results sheet."""
    from apps.grades.models import Exam
    from apps.students.models import Student
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from django.utils import timezone

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exams = Exam.objects.filter(school=request.user.school).order_by('-year', '-id')
    exam_id = request.GET.get('exam')

    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=request.user.school)
        except Exam.DoesNotExist:
            pass
    if not exam and exams.exists():
        exam = exams.first()

    if not exam:
        return HttpResponse('<h1>No exam selected</h1>', status=404)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('gender', 'first_name', 'last_name')

    rankings, subjects = _ct_build_rankings(exam, cls, students, None)

    # Class averages per subject
    subject_averages = []
    for sub in subjects:
        vals = []
        for r in rankings:
            idx = subjects.index(sub)
            if r['marks'][idx] is not None:
                vals.append(r['marks'][idx])
        subject_averages.append(round(sum(vals) / len(vals), 1) if vals else 0)

    total_avg = round(sum(r['total'] for r in rankings) / len(rankings), 1) if rankings else 0
    class_avg = round(sum(r['average'] for r in rankings) / len(rankings), 1) if rankings else 0

    def cbc(p):
        if p >= 80: return 'EE'
        if p >= 65: return 'ME'
        if p >= 50: return 'AE'
        return 'BE'

    class_grade = cbc(class_avg)

    html_string = render_to_string('pdf/class_results.html', {
        'school': request.user.school,
        'cls': cls,
        'teacher': teacher,
        'exam': exam,
        'subjects': subjects,
        'rankings': rankings,
        'subject_averages': subject_averages,
        'total_avg': total_avg,
        'class_avg': class_avg,
        'class_grade': class_grade,
        'generated_at': timezone.now(),
        'generated_by': request.user,
    })

    filename = f"results_{cls.name.replace(' ', '_')}_{exam.name.replace(' ', '_')}.pdf"
    return html_to_pdf_response(html_string, filename)


@login_required
@class_teacher_only
def class_teacher_all_report_cards_zip(request):
    """ZIP of all report card PDFs for the class (single exam)."""
    from apps.grades.models import Exam
    from apps.students.models import Student
    from apps.grades.services.report_card import (
        cbc_grade, compute_rankings, subject_positions,
        previous_exam_for, build_performance_chart,
    )
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from xhtml2pdf import pisa
    from io import BytesIO
    import zipfile
    from django.utils import timezone

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exam_id = request.GET.get('exam')
    try:
        exam = Exam.objects.get(id=exam_id, school=request.user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        return HttpResponse('<h1>Select an exam</h1>', status=400)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    # Prep rankings/positions once
    classmates = students
    rankings = compute_rankings(exam, classmates)
    positions = subject_positions(exam, classmates)
    class_size = classmates.count()

    # Buffer ZIP in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student in students:
            pdf_bytes = _render_report_card_pdf(
                request, student, exam, rankings, positions, class_size
            )
            if pdf_bytes:
                fname = f"report_{student.admission_number}_{student.full_name.replace(' ', '_')}.pdf"
                zf.writestr(fname, pdf_bytes)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="report_cards_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.zip"'
    )
    return response


@login_required
@class_teacher_only
def class_teacher_all_report_cards_merged(request):
    """Single PDF merging all report cards for the class."""
    from apps.grades.models import Exam
    from apps.students.models import Student
    from apps.grades.services.report_card import (
        compute_rankings, subject_positions,
    )
    from django.http import HttpResponse
    from io import BytesIO
    from pypdf import PdfWriter, PdfReader
    from django.utils import timezone

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exam_id = request.GET.get('exam')
    try:
        exam = Exam.objects.get(id=exam_id, school=request.user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        return HttpResponse('<h1>Select an exam</h1>', status=400)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    classmates = students
    rankings = compute_rankings(exam, classmates)
    positions = subject_positions(exam, classmates)
    class_size = classmates.count()

    writer = PdfWriter()
    for student in students:
        pdf_bytes = _render_report_card_pdf(
            request, student, exam, rankings, positions, class_size
        )
        if pdf_bytes:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    out.seek(0)

    response = HttpResponse(out.read(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="report_cards_all_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.pdf"'
    )
    return response


def _render_report_card_pdf(request, student, exam, rankings, positions, class_size):
    """Helper — returns PDF bytes for a single student's report card, or None."""
    from apps.grades.models import Grade
    from apps.grades.services.report_card import (
        cbc_grade, previous_exam_for, build_performance_chart,
    )
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from io import BytesIO
    from django.utils import timezone

    current_grades = list(
        Grade.objects.filter(student=student, exam=exam)
        .select_related('subject').order_by('subject__name')
    )
    if not current_grades:
        return None  # skip students with no grades for this exam

    total_marks = sum(float(g.marks) for g in current_grades)
    total_out_of = sum(float(g.out_of) for g in current_grades) or 1
    avg_pct = round((total_marks / total_out_of) * 100, 1) if current_grades else 0

    class_rank_info = rankings.get(student.id, {'rank': '—', 'total': total_marks, 'avg': avg_pct})

    # Previous exam + chart
    prev_exam = previous_exam_for(exam, student.school)
    previous_grades_map = {}
    if prev_exam:
        prev_qs = Grade.objects.filter(student=student, exam=prev_exam)
        previous_grades_map = {
            g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
            for g in prev_qs
        }

    current_grades_map = {
        g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        for g in current_grades
    }

    chart_path = None
    if prev_exam and previous_grades_map:
        chart_path = build_performance_chart(current_grades_map, previous_grades_map)

    grade_rows = []
    for g in current_grades:
        pct = round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        pos = positions.get(g.subject_id, {}).get(student.id, '—')
        grade_rows.append({
            'subject': g.subject.name,
            'marks': g.marks,
            'out_of': g.out_of,
            'pct': pct,
            'grade': cbc_grade(pct),
            'position': pos,
        })

    overall_grade = cbc_grade(avg_pct)

    html_string = render_to_string('pdf/report_card.html', {
        'student': student,
        'exam': exam,
        'prev_exam': prev_exam,
        'grade_rows': grade_rows,
        'avg_pct': avg_pct,
        'overall_grade': overall_grade,
        'class_rank': class_rank_info['rank'],
        'class_size': class_size,
        'total_marks': total_marks,
        'total_out_of': total_out_of,
        'chart_path': chart_path,
        'teacher_remarks': '',
        'school': student.school,
        'user': request.user,
    })

    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(src=html_string, dest=buffer, encoding='utf-8')
    if pisa_status.err:
        return None
    return buffer.getvalue()
@login_required
def invoice_student_quick(request, student_id):
    """Quick-invoice a single student from the Students & Fees page."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.finance.models import FeeStructure, Invoice
    from collections import defaultdict

    school = request.user.school
    student = get_object_or_404(Student, id=student_id, school=school)

    # Get available terms for the student's class
    fs_qs = FeeStructure.objects.filter(
        school=school, class_level=student.class_level
    ).order_by('name')

    terms = defaultdict(lambda: {'total': 0.0, 'anchor': None})
    for fs in fs_qs:
        term_part = fs.name.split(' — ', 1)[0] if ' — ' in fs.name else fs.name
        terms[term_part]['total'] += float(fs.amount_kes)
        if terms[term_part]['anchor'] is None:
            terms[term_part]['anchor'] = fs

    term_options = [
        {'name': t, 'total': d['total'], 'anchor_id': d['anchor'].id if d['anchor'] else None}
        for t, d in sorted(terms.items())
    ]

    if request.method == 'POST':
        term_name = request.POST.get('term', '').strip()
        custom_amount = request.POST.get('custom_amount', '').strip()
        override = request.POST.get('override', '') == '1'

        if not term_name:
            messages.error(request, 'Please pick a term.')
            return redirect('invoice_student_quick', student_id=student.id)

        # Determine anchor
        term_fs = fs_qs.filter(name__startswith=f"{term_name} —")
        if not term_fs.exists():
            messages.error(request, f'No fees for "{term_name}".')
            return redirect('invoice_student_quick', student_id=student.id)
        anchor = term_fs.first()

        # Determine amount
        if override and custom_amount:
            try:
                amount = float(custom_amount)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'Invalid custom amount.')
                return redirect('invoice_student_quick', student_id=student.id)
        else:
            amount = sum(float(f.amount_kes) for f in term_fs)

        invoice, created = Invoice.objects.get_or_create(
            student=student,
            fee_structure=anchor,
            defaults={'amount_due': amount, 'due_date': anchor.due_date},
        )
        if created:
            messages.success(
                request,
                f'✅ Invoice created for {student.full_name}: KES {amount:,.0f}.'
            )
        else:
            invoice.amount_due = amount
            invoice.due_date = anchor.due_date
            invoice.save(update_fields=['amount_due', 'due_date'])
            invoice.update_status()
            messages.info(request, f'Invoice updated: KES {amount:,.0f}.')
        return redirect('accountant_students')
    return render(request, 'dashboard/invoice_student_quick.html', {
        'student': student,
        'term_options': term_options,
    })


@login_required
def record_payment(request, invoice_id):
    """Record a manual payment against an invoice."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment

    invoice = get_object_or_404(
        Invoice, id=invoice_id, student__school=request.user.school
    )

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        method = request.POST.get('method', 'cash')
        external_ref = request.POST.get('external_reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []

        try:
            amount = float(amount)
            if amount <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Please enter a valid amount.')
            amount = 0

        if method not in [c[0] for c in Payment.Method.choices]:
            errors.append('Invalid payment method.')

        if method in ('mpesa', 'airtel', 'bank', 'cheque') and not external_ref:
            errors.append(f'Please enter the {method.upper()} transaction reference.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('record_payment', invoice_id=invoice.id)

        try:
            payment = Payment.objects.create(
                invoice=invoice,
                amount_kes=amount,
                method=method,
                external_reference=external_ref,
                notes=notes,
                recorded_by=request.user,
            )
            messages.success(
                request,
                f'Payment recorded. Transaction: {payment.reference} '
                f'(KES {amount:,.2f} via {payment.get_method_display()})'
            )
            return redirect('accountant_invoices')
        except Exception as e:
            messages.error(request, f'Error recording payment: {e}')
            return redirect('record_payment', invoice_id=invoice.id)

    # GET — render form
    return render(request, 'dashboard/record_payment.html', {
        'invoice': invoice,
        'methods': Payment.Method.choices,
    })
@login_required
def financial_report_pdf(request):
    """Generate a financial report PDF for the selected period."""
    if request.user.role not in ('accountant', 'school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment, Expenditure
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from django.db.models import Sum, F
    from django.utils import timezone
    from datetime import date, timedelta
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    school = user.school
    today = date.today()

    # ---------- Period selection ----------
    period = request.GET.get('period', 'month')
    if period == 'custom':
        try:
            start_date = date.fromisoformat(request.GET.get('start', ''))
            end_date = date.fromisoformat(request.GET.get('end', ''))
        except (ValueError, TypeError):
            start_date = today.replace(day=1)
            end_date = today
        period_label = f'{start_date.strftime("%d %b %Y")} — {end_date.strftime("%d %b %Y")}'
    elif period == 'term':
        start_date = today - timedelta(days=90)
        end_date = today
        period_label = 'Last 90 Days'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = f'Year {today.year}'
    else:
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')

    # ---------- Collections ----------
    payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date,
    ).select_related('invoice__student')

    total_collected = float(payments.aggregate(t=Sum('amount_kes'))['t'] or 0)

    method_breakdown = {}
    for row in payments.values('method').annotate(t=Sum('amount_kes')):
        label = dict(Payment.Method.choices).get(row['method'], row['method'])
        method_breakdown[label] = float(row['t'] or 0)

    # ---------- Expenditure ----------
    expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=start_date,
        spent_on__lte=end_date,
    )
    total_expenditure = float(expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0)

    category_breakdown = {}
    for row in expenditures.values('category').annotate(t=Sum('amount_kes')):
        label = dict(Expenditure.Category.choices).get(row['category'], row['category'])
        category_breakdown[label] = float(row['t'] or 0)

    net_position = total_collected - total_expenditure

    # ---------- Outstanding ----------
    outstanding_agg = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))
    total_outstanding = float(outstanding_agg['t'] or 0)

    # ---------- Per-class breakdown ----------
    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_students = list(
            Student.objects.filter(
                school=school, class_level=cls.name, is_active=True
            ).values_list('id', flat=True)
        )
        if not class_students:
            continue

        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_students,
                paid_at__date__gte=start_date,
                paid_at__date__lte=end_date,
            ).aggregate(t=Sum('amount_kes'))['t'] or 0
        )

        class_breakdown.append({
            'class_name': cls.name,
            'students': len(class_students),
            'collected': class_collected,
        })

    class_breakdown.sort(key=lambda x: x['collected'], reverse=True)

    # ---------- Previous period ----------
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    prev_collected = float(
        Payment.objects.filter(
            invoice__student__school=school,
            paid_at__date__gte=prev_start,
            paid_at__date__lte=prev_end,
        ).aggregate(t=Sum('amount_kes'))['t'] or 0
    )
    prev_expenditure = float(
        Expenditure.objects.filter(
            school=school, spent_on__gte=prev_start, spent_on__lte=prev_end,
        ).aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    html_string = render_to_string('pdf/financial_report.html', {
        'school': school,
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'prev_start': prev_start,
        'prev_end': prev_end,
        'total_collected': total_collected,
        'total_expenditure': total_expenditure,
        'total_outstanding': total_outstanding,
        'net_position': net_position,
        'prev_collected': prev_collected,
        'prev_expenditure': prev_expenditure,
        'method_breakdown': method_breakdown,
        'category_breakdown': category_breakdown,
        'class_breakdown': class_breakdown,
        'generated_at': timezone.now(),
        'generated_by': user,
    })

    filename = f'financial_report_{start_date.isoformat()}_{end_date.isoformat()}.pdf'
    return html_to_pdf_response(html_string, filename)
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


