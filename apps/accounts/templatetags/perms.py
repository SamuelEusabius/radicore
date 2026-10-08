"""
Template filters for permission checks.

Usage in templates:
    {% load perms %}
    {% if user|can:"exams:publish" %}
        <button>Publish Exam</button>
    {% endif %}
"""
from django import template

from apps.accounts.permissions import has_perm

register = template.Library()


@register.filter(name='can')
def can(user, perm_string):
    """
    Check if user has permission.
    perm_string format: 'resource:action'
    """
    if not perm_string or ':' not in perm_string:
        return False
    resource, action = perm_string.split(':', 1)
    return has_perm(user, resource.strip(), action.strip())


@register.filter(name='has_role')
def has_role(user, role_string):
    """
    Check if user has a role. Supports comma-separated roles:
        {% if user|has_role:"principal,deputy_admin" %}
    """
    if not user or not user.is_authenticated:
        return False
    wanted = [r.strip() for r in str(role_string).split(',')]
    return getattr(user, 'role', None) in wanted