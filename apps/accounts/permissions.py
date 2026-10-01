from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    allowed_roles = []
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in self.allowed_roles


class IsSuperAdmin(RolePermission):  allowed_roles = ['super_admin']
class IsSchoolAdmin(RolePermission): allowed_roles = ['school_admin', 'super_admin']
class IsTeacher(RolePermission):     allowed_roles = ['teacher', 'school_admin', 'super_admin']
class IsParent(RolePermission):      allowed_roles = ['parent']
class IsAccountant(RolePermission):  allowed_roles = ['accountant', 'school_admin', 'super_admin']
class IsStudent(RolePermission):     allowed_roles = ['student']


class SameSchoolOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'super_admin':
            return True
        return getattr(obj, 'school_id', None) == request.user.school_id