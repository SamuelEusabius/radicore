"""
ElimuCore permission layer.

Single source of truth for what each role can do.

Two ways to use:
  1. In views:      @require_perm('exams', 'publish')
  2. In code:       if has_perm(user, 'exams', 'publish'): ...

Resources are strings — stable identifiers used across the codebase.
Actions are strings — see ACTION_* constants below.

Special value '*' means "all resources, all actions".
"""
from functools import wraps

from django.core.exceptions import PermissionDenied

from .roles import Role


# ==========================================================
# ACTION CONSTANTS
# ==========================================================
ACTION_VIEW      = 'view'
ACTION_VIEW_OWN  = 'view_own'          # only own records (student, parent)
ACTION_CREATE    = 'create'
ACTION_EDIT      = 'edit'
ACTION_DELETE    = 'delete'
ACTION_APPROVE   = 'approve'
ACTION_PUBLISH   = 'publish'
ACTION_FLAGS     = 'flags'             # summary/flag visibility only
ACTION_SCOPED    = 'scoped'            # only assigned subsets (class/subject)
ACTION_VIEW_FINANCE = 'view_finance'
ACTION_VIEW_HEALTH  = 'view_health'
ACTION_VIEW_BOARDING = 'view_boarding'


# ==========================================================
# ROLE → RESOURCE → ACTIONS MATRIX
# ==========================================================
# '*' at the top level means "this role has full access to everything".
# Otherwise, the dict maps resource names → set of allowed actions.

ROLE_PERMISSIONS = {

    # ---------- PLATFORM ----------
    Role.SUPER_ADMIN: {
        # Super Admin is public-schema only. No tenant data access.
        'schools':       {'view', 'create', 'edit', 'delete'},
        'subscriptions': {'view', 'create', 'edit', 'delete'},
        'modules':       {'view', 'edit'},
        'users':         {'view'},        # view-only across platform
        'audit':         {'view'},
    },

    # ---------- SCHOOL LEADERSHIP ----------
    Role.PRINCIPAL: {
        'students':      {'view', 'create', 'edit', 'delete'},
        'teachers':      {'view', 'create', 'edit', 'delete'},
        'staff':         {'view', 'create', 'edit', 'delete'},
        'parents':       {'view'},
        'academics':     {'view', 'create', 'edit', 'delete', 'approve', 'publish'},
        'attendance':    {'view', 'create', 'edit'},
        'grades':        {'view', 'create', 'edit', 'approve', 'publish'},
        'exams':         {'view', 'create', 'edit', 'approve', 'publish'},
        'finance':       {'view', 'approve'},
        'discipline':    {'view', 'create', 'edit', 'approve'},
        'transport':     {'view', 'approve'},
        'boarding':      {'view', 'approve'},
        'security':      {'view'},
        'procurement':   {'view', 'approve'},
        'inventory':     {'view'},
        'health':        {'view', 'flags'},
        'library':       {'view'},
        'lab':           {'view'},
        'talent':        {'view', 'approve'},
        'compliance':    {'view', 'edit'},
        'audit':         {'view'},
        'notifications': {'view', 'create'},
        'reports':       {'view', 'create'},
    },

    Role.DEPUTY_ADMIN: {
        'students':       {'view'},
        'teachers':       {'view'},
        'staff':          {'view', 'edit'},
        'parents':        {'view'},
        'attendance':     {'view', 'edit'},
        'discipline':     {'view', 'create', 'edit', 'approve'},
        'leave_requests': {'view', 'approve'},
        'duty_roster':    {'view', 'create', 'edit'},
        'transport':      {'view', 'edit'},
        'boarding':       {'view', 'edit'},
        'security':       {'view', 'edit'},
        'procurement':    {'view', 'approve'},
        'inventory':      {'view'},
        'health':         {'view', 'flags'},
        'exams':          {'view', 'flags'},
        'reports':        {'view'},
    },

    Role.DEPUTY_ACADEMICS: {
        'students':       {'view'},
        'teachers':       {'view'},
        'staff':          {'view'},
        'parents':        {'view'},
        'academics':      {'view', 'create', 'edit', 'publish'},
        'attendance':     {'view'},
        'grades':         {'view', 'create', 'edit', 'approve', 'publish'},
        'exams':          {'view', 'create', 'edit', 'approve', 'publish'},
        'mark_sheets':    {'view', 'edit', 'approve'},
        'timetable':      {'view', 'create', 'edit', 'publish'},
        'syllabus':       {'view', 'edit'},
        'lesson_plans':   {'view', 'approve'},
        'subject_alloc':  {'view', 'create', 'edit'},
        'discipline':     {'view', 'flags'},
        'lab':            {'view'},
        'reports':        {'view', 'create'},
    },

    Role.DIRECTOR_OF_STUDIES: {
        'students':       {'view'},
        'teachers':       {'view'},
        'academics':      {'view', 'edit'},
        'attendance':     {'view'},
        'grades':         {'view', 'create', 'edit'},
        'exams':          {'view', 'create', 'edit'},
        'mark_sheets':    {'view', 'edit'},
        'timetable':      {'view', 'edit'},
        'syllabus':       {'view', 'edit'},
        'lesson_plans':   {'view'},
        'subject_alloc':  {'view', 'edit'},
    },

    # ---------- TEACHING ----------
    Role.CLASS_TEACHER: {
        'students':    {'view', 'scoped'},
        'attendance':  {'view', 'create', 'edit'},
        'grades':      {'view', 'create', 'edit'},
        'exams':       {'view', 'scoped'},
        'talent':      {'view'},
    },

    Role.TEACHER: {
        'students':    {'view', 'scoped'},
        'attendance':  {'view', 'create', 'edit'},
        'grades':      {'view', 'create', 'edit'},
        'exams':       {'view', 'scoped'},
        'lesson_plans': {'view', 'create', 'edit'},
    },

    # ---------- FINANCE / ADMIN ----------
    Role.ACCOUNTANT: {
        'students':   {'view', 'view_finance'},
        'finance':    {'view', 'create', 'edit'},
        'invoices':   {'view', 'create', 'edit'},
        'mpesa':      {'view', 'create'},
        'reports':    {'view', 'create'},
    },

    Role.SECRETARY: {
        'students':      {'view', 'create', 'edit'},
        'parents':       {'view', 'create', 'edit'},
        'staff':         {'view'},
        'admissions':    {'view', 'create', 'edit'},
        'communication': {'view', 'create'},
        'documents':     {'view', 'create'},
    },

    # ---------- OPERATIONS ----------
    Role.STORE_KEEPER: {
        'inventory':  {'view', 'create', 'edit'},
        'procurement': {'view', 'create'},
    },

    Role.BOARDING_MASTER: {
        'students':   {'view', 'view_boarding'},
        'boarding':   {'view', 'create', 'edit'},
    },

    Role.CHIEF_CHEF: {
        'kitchen':    {'view', 'create', 'edit'},
        'inventory':  {'view'},
    },

    Role.SECURITY_OFFICER: {
        'students':   {'view'},
        'security':   {'view', 'create', 'edit'},
        'visitors':   {'view', 'create', 'edit'},
        'discipline': {'view', 'create'},
    },

    Role.DRIVER: {
        'transport':  {'view', 'view_own'},
    },

    Role.LAB_TECHNICIAN: {
        'lab':        {'view', 'create', 'edit'},
        'inventory':  {'view'},
    },

    Role.LIBRARIAN: {
        'library':    {'view', 'create', 'edit'},
    },

    Role.NURSE: {
        'students':   {'view', 'view_health'},
        'health':     {'view', 'create', 'edit'},
    },

    # ---------- END USERS ----------
    Role.STUDENT: {
        'self':       {'view'},
        'exams':      {'view_own'},
        'grades':     {'view_own'},
        'attendance': {'view_own'},
        'finance':    {'view_own'},
        'talent':     {'view_own', 'edit'},
        'timetable':  {'view_own'},
    },

    Role.PARENT: {
        'children':   {'view'},
        'exams':      {'view_own'},
        'grades':     {'view_own'},
        'attendance': {'view_own'},
        'finance':    {'view_own', 'create'},   # pay fees
        'communication': {'view', 'create'},
    },
}


# ==========================================================
# CORE CHECK
# ==========================================================
def has_perm(user, resource, action):
    """
    Return True if user is allowed to perform action on resource.

    Examples:
        has_perm(request.user, 'exams', 'publish')
        has_perm(request.user, 'finance', 'approve')
    """
    if not user or not user.is_authenticated:
        return False

    role = getattr(user, 'role', None)
    if not role:
        return False

    # Super Admin bypass — but only for what their role allows.
    perms = ROLE_PERMISSIONS.get(role)
    if perms == '*':
        return True
    if not perms:
        return False

    allowed = perms.get(resource)
    if not allowed:
        return False

    return action in allowed


# ==========================================================
# DECORATORS
# ==========================================================
def require_perm(resource, action):
    """
    View decorator. Raises PermissionDenied if the user lacks the perm.

    Usage:
        @require_perm('exams', 'publish')
        def publish_exam(request, exam_id): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_perm(request.user, resource, action):
                raise PermissionDenied(
                    f"You do not have permission to {action} {resource}."
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def user_has_role(*roles):
    """
    View decorator. Raises PermissionDenied if the user's role isn't in `roles`.

    Usage:
        @user_has_role(Role.PRINCIPAL, Role.DEPUTY_ADMIN)
        def principal_dashboard(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            if request.user.role not in [r.value if hasattr(r, 'value') else r for r in roles]:
                raise PermissionDenied("Your role cannot access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator



# ==========================================================
# DRF PERMISSION CLASSES
# ==========================================================
# Used by DRF views via permission_classes=[...].
# These wrap the role matrix and keep legacy names working.

from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    message = "Super Admin access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.SUPER_ADMIN
        )


class IsSchoolAdmin(BasePermission):
    """
    Legacy name — maps to Principal.
    Kept because multiple apps import this exact name.
    """
    message = "School administrator access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.PRINCIPAL, Role.SUPER_ADMIN)
        )


class IsPrincipal(BasePermission):
    message = "Principal access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.PRINCIPAL
        )


class IsDeputyAdmin(BasePermission):
    message = "Deputy Principal (Administration) access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.DEPUTY_ADMIN
        )


class IsDeputyAcademics(BasePermission):
    message = "Deputy Principal (Academics) access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.DEPUTY_ACADEMICS
        )


class IsTeacher(BasePermission):
    message = "Teacher access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (Role.TEACHER, Role.CLASS_TEACHER)
        )


class IsAccountant(BasePermission):
    message = "Accountant access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ACCOUNTANT
        )


class IsStudent(BasePermission):
    message = "Student access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.STUDENT
        )


class IsParent(BasePermission):
    message = "Parent access only."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.PARENT
        )


class IsStaff(BasePermission):
    """Any school staff role (not student/parent/super_admin)."""
    message = "Staff access only."

    def has_permission(self, request, view):
        from .roles import SCHOOL_STAFF
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [r.value for r in SCHOOL_STAFF]


class HasPerm(BasePermission):
    """
    DRF permission class that uses the role matrix.

    Set on the view:
        perm_resource = 'exams'
        perm_action = 'publish'
    """
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        resource = getattr(view, 'perm_resource', None)
        action = getattr(view, 'perm_action', None)
        if not resource or not action:
            return False
        return has_perm(request.user, resource, action)