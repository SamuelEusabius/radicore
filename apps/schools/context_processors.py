def current_school(request):
    return {'current_school': getattr(request, 'school', None)}

def notifications_context(request):
    if not request.user.is_authenticated:
        return {'unread_notifications': 0}
    try:
        from apps.notifications.models import Notification
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {'unread_notifications': count}
    except Exception:
        return {'unread_notifications': 0}