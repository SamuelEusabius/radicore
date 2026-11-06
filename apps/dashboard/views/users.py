"""
User & Staff views:
- Non-teaching staff list/add/delete
- User management (deactivate, delete, change role)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q

from apps.accounts.roles import (
    Role,
    can_create_role,
    creatable_roles_for,
)


User = get_user_model()


# ============================================================
# NON-TEACHING STAFF
# ============================================================

@login_required
def staff_list(request):
    """List non-teaching staff with filters and stats."""
    if request.user.role not in ('principal', 'deputy_admin', 'secretary', 'ict_officer'):
        return redirect('dashboard_home')
    
    from apps.staff.models import NonTeachingStaff

    school = request.user.school
    base_qs = NonTeachingStaff.objects.filter(school=school)

    search = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs.order_by('role', 'full_name')

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(id_number__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    if role_filter:
        qs = qs.filter(role=role_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

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


@login_required
def add_staff(request):
    if request.user.role not in ('principal', 'super_admin'):
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

        messages.success(request, f'Staff "{staff.full_name}" added successfully.')
        return redirect('staff_list')

    return render(request, 'dashboard/add_staff.html', {
        'roles': NonTeachingStaff.Role.choices,
    })


@login_required
def delete_staff(request, staff_id):
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    staff = get_object_or_404(NonTeachingStaff, id=staff_id, school=request.user.school)

    if request.method == 'POST':
        name = staff.full_name
        staff.delete()
        messages.success(request, f'Staff "{name}" deleted.')
        return redirect('staff_list')

    return render(request, 'dashboard/delete_staff.html', {'staff': staff})


# ============================================================
# USER MANAGEMENT
# ============================================================

@login_required
def user_deactivate(request, user_id):
    """Toggle user is_active (deactivate or reactivate)."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    if request.method != 'POST':
        return redirect('manage_users')

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    if target.id == request.user.id:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('manage_users')

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
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        status = 'activated' if target.is_active else 'deactivated'
        messages.success(request, f'{target.email} has been {status}.')

    return redirect('manage_users')


@login_required
def user_delete(request, user_id):
    """Hard-delete a user (with safety checks)."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    if target.id == request.user.id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('manage_users')

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
    """Change a user's role, governed by the central role policy."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    if target.id == request.user.id:
        messages.error(request, 'You cannot change your own role.')
        return redirect('manage_users')

    # Roles this actor may assign — single source of truth.
    role_choices = creatable_roles_for(request.user.role)

    if request.method == 'POST':
        new_role = request.POST.get('role', '').strip()

        if new_role not in dict(Role.choices):
            messages.error(request, 'Invalid role.')
            return redirect('manage_users')

        if not can_create_role(request.user.role, new_role):
            messages.error(request, 'You are not allowed to assign that role.')
            return redirect('manage_users')

        old_role = target.get_role_display()
        target.role = new_role
        target.save(update_fields=['role'])

        messages.success(
            request,
            f'{target.email} role changed from {old_role} to {target.get_role_display()}.',
        )
        return redirect('manage_users')

    return render(request, 'dashboard/user_change_role.html', {
        'target': target,
        'role_choices': role_choices,
    })


# ============================================================
# SCHOOL ADMIN — CHANGE USER PASSWORD
# ============================================================

@login_required
def user_change_password(request, user_id):
    """School Admin changes password for a user in their school."""
    if request.user.role not in ('principal', 'super_admin'):
        messages.error(request, 'Access denied.')
        return redirect('manage_users')

    if request.user.role == 'super_admin':
        target = get_object_or_404(User, id=user_id)
    else:
        target = get_object_or_404(User, id=user_id, school=request.user.school)

    if target.role == 'super_admin' and request.user.role != 'super_admin':
        messages.error(request, 'You do not have permission to modify a Super Admin.')
        return redirect('manage_users')

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not new_password or len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return redirect('user_change_password', user_id=target.id)

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('user_change_password', user_id=target.id)

        target.set_password(new_password)
        target.save(update_fields=['password'])
        messages.success(request, f'Password updated for {target.email}.')
        return redirect('manage_users')

    return render(request, 'dashboard/user_change_password.html', {
        'target': target,
    })
    
@login_required
def edit_staff(request, staff_id):
    """Edit an existing non-teaching staff member."""
    if request.user.role not in ('principal', 'super_admin', 'deputy_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    staff = get_object_or_404(NonTeachingStaff, id=staff_id, school=request.user.school)
    
    roles = NonTeachingStaff.Role.choices

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        role = request.POST.get('role', '')
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        date_of_birth = request.POST.get('date_of_birth') or None
        hire_date = request.POST.get('hire_date') or None
        salary = request.POST.get('salary') or None
        is_active = request.POST.get('is_active') == 'on'

        if not full_name or not id_number or not role:
            messages.error(request, 'Full Name, National ID, and Role are required.')
        else:
            staff.full_name = full_name
            staff.id_number = id_number
            staff.role = role
            staff.phone = phone
            staff.email = email
            staff.date_of_birth = date_of_birth
            staff.hire_date = hire_date
            staff.salary = salary
            staff.is_active = is_active

            if 'photo' in request.FILES:
                staff.photo = request.FILES['photo']

            staff.save()
            messages.success(request, f'Staff member "{staff.full_name}" updated successfully.')
            return redirect('staff_list')

    return render(request, 'dashboard/add_staff.html', {
        'is_edit': True,
        'staff': staff,
        'roles': roles,
        'form_data': {
            'full_name': staff.full_name,
            'id_number': staff.id_number,
            'role': staff.role,
            'phone': staff.phone,
            'email': staff.email,
            'date_of_birth': staff.date_of_birth.strftime('%Y-%m-%d') if staff.date_of_birth else '',
            'hire_date': staff.hire_date.strftime('%Y-%m-%d') if staff.hire_date else '',
            'salary': staff.salary,
            'is_active': staff.is_active,
        }
    })

@login_required
def staff_id_card(request, staff_id):
    """Print-ready view for a Non-Teaching Staff ID card."""
    if request.user.role not in ('principal', 'secretary', 'deputy_admin', 'ict_officer'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    school = request.user.school
    staff = get_object_or_404(NonTeachingStaff, id=staff_id, school=school)

    return render(request, 'dashboard/staff_id_card.html', {
        'staff': staff,
        'school': school,
    })
    
    # ==========================================================
# ICT OFFICER VIEWS
# ==========================================================

@login_required
def ict_dashboard(request):
    """Dashboard for the ICT Officer showing system usage stats."""
   # Allow both Principal and ICT Officer
    if request.user.role not in ('ict_officer', 'principal',):
        return redirect('dashboard_home')
    from apps.schools.models import SchoolModule
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.parents.models import Parent

    school = request.user.school

    # 1. Safely check if the module is enabled.
    module_obj, created = SchoolModule.objects.get_or_create(
        school=school,
        module='ict',
        defaults={'is_enabled': True}
    )

    if not module_obj.is_enabled:
        messages.error(request, "ICT Module is not enabled for this school. Please contact the Principal.")
        return redirect('dashboard_home')

    # 2. Load the stats (Fixed Parent query to use user__school)
    context = {
        'school': school,
        'total_students': Student.objects.filter(school=school, is_active=True).count(),
        'total_teachers': Teacher.objects.filter(school=school, is_active=True).count(),
        'total_parents': Parent.objects.filter(user__school=school).count(),
    }
    
    return render(request, 'dashboard/ict_dashboard.html', context)
@login_required
def ict_upload_student_photo(request, student_id):
    """Allow ICT Officer to update a student's photo."""
    if request.user.role not in ('ict_officer', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    if request.method == 'POST' and request.FILES.get('photo'):
        student.photo = request.FILES['photo']
        student.save()
        messages.success(request, f"Photo updated for {student.first_name}.")
        return redirect('students_list')

    return render(request, 'dashboard/upload_photo.html', {
        'person_name': f"{student.first_name} {student.last_name}",
        'return_url': 'students_list'
    })


@login_required
def ict_upload_teacher_photo(request, teacher_id):
    """Allow ICT Officer to update a teacher's photo."""
    if request.user.role not in ('ict_officer', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.teachers.models import Teacher
    teacher = get_object_or_404(Teacher, id=teacher_id, school=request.user.school)

    if request.method == 'POST' and request.FILES.get('photo'):
        teacher.photo = request.FILES['photo']
        teacher.save()
        messages.success(request, f"Photo updated for {teacher.user.get_full_name()}.")
        return redirect('teachers_list')

    return render(request, 'dashboard/upload_photo.html', {
        'person_name': f"{teacher.user.get_full_name()}",
        'return_url': 'teachers_list'
    })


@login_required
def ict_upload_staff_photo(request, staff_id):
    """Allow ICT Officer to update a non-teaching staff's photo."""
    if request.user.role not in ('ict_officer', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.staff.models import NonTeachingStaff
    staff = get_object_or_404(NonTeachingStaff, id=staff_id, school=request.user.school)

    if request.method == 'POST' and request.FILES.get('photo'):
        staff.photo = request.FILES['photo']
        staff.save()
        messages.success(request, f"Photo updated for {staff.full_name}.")
        return redirect('staff_list')

    return render(request, 'dashboard/upload_photo.html', {
        'person_name': staff.full_name,
        'return_url': 'staff_list'
    })