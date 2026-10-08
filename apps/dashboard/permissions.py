"""
Central permission helpers — single source of truth for role checks.
"""
from django.shortcuts import redirect
from django.contrib import messages


# ============================================================
# ROLE CONSTANTS
# ============================================================

SCHOOL_ROLES = (
    'principal', 'teacher', 'accountant', 'parent', 'student',
    'driver', 'librarian', 'lab_technician', 'nurse', 'chief_chef',
)

DASHBOARD_ROLES = ('principal', 'teacher', 'accountant', 'parent', 'student')

DEPARTMENT_ROLES = ('driver', 'librarian', 'lab_technician', 'nurse', 'chief_chef')

SCHOOL_MANAGEMENT_ROLES = ('principal',)  # ← NO super_admin


# ============================================================
# HELPERS
# ============================================================

def is_school_staff(user):
    """True if user belongs to a school (not super admin)."""
    return user.is_authenticated and user.role in SCHOOL_ROLES


def is_school_admin(user):
    """True only for school admins."""
    return user.is_authenticated and user.role == 'principal'


def is_super_admin(user):
    """True only for platform super admins."""
    return user.is_authenticated and user.role == 'super_admin'


def school_management_required(view_func):
    """
    Decorator: only School Admin can access.
    Super Admin is BLOCKED (they have no school).
    """
    def wrapper(request, *args, **kwargs):
        if not is_school_admin(request.user):
            messages.error(request, 'Access denied. Only school administrators can access this page.')
            return redirect('dashboard_home')
        return view_func(request, *args, **kwargs)
    return wrapper


def super_admin_required(view_func):
    """
    Decorator: only Super Admin can access.
    """
    def wrapper(request, *args, **kwargs):
        if not is_super_admin(request.user):
            messages.error(request, 'Access denied. Super Admin only.')
            return redirect('dashboard_home')
        return view_func(request, *args, **kwargs)
    return wrapper