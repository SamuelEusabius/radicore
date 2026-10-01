"""
User & Staff views:
- Non-teaching staff list/add/delete
- User management (deactivate, delete, change role)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone

from apps.accounts.decorators import (
    role_required, school_staff_only, super_admin_only,
)

User = get_user_model()


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


