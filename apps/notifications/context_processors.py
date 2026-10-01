def topbar_badge_count(request):
    """Provides topbar bell badge count for authenticated users."""
    if not request.user.is_authenticated:
        return {'topbar_badge_count': 0}

    try:
        from apps.notifications.models import Notification, Alert

        unread_notifs = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()

        if request.user.role in ('school_admin', 'super_admin'):
            unresolved_alerts = 0
            if getattr(request.user, 'school', None):
                unresolved_alerts = Alert.objects.filter(
                    status__in=['new', 'reviewing'],
                    school=request.user.school,
                ).count()
        else:
            unresolved_alerts = 0

        return {'topbar_badge_count': unread_notifs + unresolved_alerts}
    except Exception:
        return {'topbar_badge_count': 0}