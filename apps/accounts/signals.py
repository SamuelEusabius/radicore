from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def create_secure_session(sender, request, user, **kwargs):
    """
    Fires on every successful login.
    Creates the 95-char secure session and sets the HttpOnly cookie.
    Enforces single-device policy by killing all older sessions.
    """
    from apps.accounts.models import UserSession

    # 1. Kill ALL existing active sessions for this user (single-device policy)
    killed = UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
    if killed:
        print(f">>> KILLED {killed} OLD SESSIONS FOR {user.email} <<<")

    # 2. Create a new session
    session = UserSession(
        user=user,
        school=user.school,
        ip_address=request.META.get('REMOTE_ADDR'),
        device=request.META.get('HTTP_USER_AGENT', 'Unknown')[:255]
    )
    raw_key = session.generate_key()
    session.save()
    
    print(f">>> NEW SESSION: {user.email} from {session.ip_address} <<<")

    # 3. Attach the raw key so middleware can read it
    request._rc_raw_session_key = raw_key