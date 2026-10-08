"""
Tenant-scoped querysets and managers.

Any model that has a `school` FK (or is tenant-owned) should use TenantManager.

Usage in views:
    Student.objects.for_school(request.school).all()
    Student.objects.for_user(request.user).all()

If school is None → returns none() (empty queryset).
This is fail-safe: a bug that forgets to pass a school returns nothing
rather than leaking every tenant's data.
"""
from django.db import models

from apps.accounts.roles import Role


class TenantQuerySet(models.QuerySet):

    def for_school(self, school):
        """Filter to a specific school. Returns empty if school is None."""
        if school is None:
            return self.none()
        return self.filter(school=school)

    def for_user(self, user):
        """
        Filter to the schools a user can see.

        - super_admin → all (public-schema role; usually only platform data)
        - school-bound users → only their own school
        - anonymous → nothing
        """
        if not user or not user.is_authenticated:
            return self.none()

        if getattr(user, 'role', None) == Role.SUPER_ADMIN:
            # Super Admin should not see tenant data per our architecture.
            # Return none() unless explicitly overridden by a view.
            return self.none()

        school = getattr(user, 'school', None)
        if school is None:
            return self.none()

        return self.filter(school=school)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager for tenant-owned models."""
    pass