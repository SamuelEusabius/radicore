"""
Template tags for checking school module status.

Usage:
    {% load module_tags %}
    {% has_module current_school 'library' as show_library %}
    {% if show_library %} ... {% endif %}

    {# or inline: #}
    {% if_school_has_module current_school 'wallet' %}
        Wallet link
    {% endif_school_has_module %}
"""

from django import template

register = template.Library()


@register.simple_tag
def has_module(school, module_code):
    """
    Return True if the school has the given module enabled.
    Cached per school on the request object to avoid repeated queries.
    """
    if not school:
        return False

    from apps.schools.models import SchoolModule
    return SchoolModule.objects.filter(
        school=school,
        module=module_code,
        is_enabled=True,
    ).exists()


@register.simple_tag(takes_context=True)
def enabled_modules(context):
    """
    Return a set of enabled module codes for the current school.
    Attaches to request to avoid repeated queries in same request.

    Usage:
        {% enabled_modules as modules %}
        {% if 'library' in modules %} ... {% endif %}
    """
    request = context.get('request')
    school = getattr(request.user, 'school', None) if request and request.user.is_authenticated else None

    if not school:
        return set()

    # Cache on request
    cache_attr = '_enabled_modules_cache'
    if hasattr(request, cache_attr):
        return getattr(request, cache_attr)

    from apps.schools.models import SchoolModule
    codes = set(
        SchoolModule.objects.filter(
            school=school, is_enabled=True
        ).values_list('module', flat=True)
    )
    setattr(request, cache_attr, codes)
    return codes