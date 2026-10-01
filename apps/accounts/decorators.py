"""
Role-based access decorators.
Use these to lock dashboards to specific roles.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*allowed_roles):
    """
    Decorator — only allows users with the specified roles.

    Usage:
        @role_required('teacher')
        def teacher_dash(request): ...

        @role_required('school_admin', 'super_admin')
        def school_admin_dash(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('/accounts/login/')

            user_role = getattr(request.user, 'role', None)

            if user_role not in allowed_roles:
                messages.error(
                    request,
                    f'Access denied. This dashboard is for '
                    f'{", ".join(allowed_roles)} only.'
                )
                # Redirect to their own dashboard
                return redirect('redirect_to_own_dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def super_admin_only(view_func):
    """Only super admins."""
    return role_required('super_admin')(view_func)


def school_staff_only(view_func):
    """School admins + super admins (support access)."""
    return role_required('school_admin', 'super_admin')(view_func)


def teacher_only(view_func):
    """Only teachers."""
    return role_required('teacher')(view_func)


def parent_only(view_func):
    """Only parents."""
    return role_required('parent')(view_func)


def accountant_only(view_func):
    """Only accountants."""
    return role_required('accountant')(view_func)


def student_only(view_func):
    """Only students."""
    return role_required('student')(view_func)


def class_teacher_only(view_func):
    """Only teachers who are class teachers."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')

        if request.user.role != 'teacher':
            messages.error(request, 'Access denied.')
            return redirect('redirect_to_own_dashboard')

        # Check if the teacher is a class teacher
        try:
            teacher = request.user.teacher_profile
            if not teacher.is_class_teacher or not teacher.current_class:
                messages.error(request, 'You are not assigned as a class teacher.')
                return redirect('dash_teacher')
        except Exception:
            messages.error(request, 'Teacher profile not found.')
            return redirect('dash_teacher')

        return view_func(request, *args, **kwargs)

    return wrapper