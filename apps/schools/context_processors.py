"""
Context processors for the schools app.

Automatically available in every template.
"""


def current_school(request):
    """Make current school available in all templates."""
    return {'current_school': getattr(request, 'school', None)}


def notifications_context(request):
    """Unread notification count for the header bell icon."""
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    try:
        from apps.notifications.models import Notification
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {'unread_notifications': count}
    except Exception:
        return {'unread_notifications': 0}


def enabled_modules(request):
    """
    Inject set of enabled module codes for the current user's school.

    Usage in templates:
        {% if 'library' in enabled_modules %} ... {% endif %}

    Cached on request object to avoid repeated DB queries.
    """
    if not request.user.is_authenticated:
        return {'enabled_modules': set()}

    school = getattr(request.user, 'school', None)
    if not school:
        return {'enabled_modules': set()}

    # Cache on request
    if hasattr(request, '_enabled_modules_cache'):
        return {'enabled_modules': request._enabled_modules_cache}

    try:
        from apps.schools.models import SchoolModule
        codes = set(
            SchoolModule.objects.filter(
                school=school, is_enabled=True
            ).values_list('module', flat=True)
        )
    except Exception:
        codes = set()

    request._enabled_modules_cache = codes
    return {'enabled_modules': codes}