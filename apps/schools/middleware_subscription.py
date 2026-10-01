"""
Middleware to block users of inactive schools from accessing the system.
Runs AFTER authentication.
"""

from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404


# URLs always allowed (even for blocked schools)
ALLOWED_URL_NAMES = {
    'account_logout',
    'account_login',
    'account_reset_password',
    'account_reset_password_done',
    'account_reset_password_from_key',
    'account_reset_password_from_key_done',
    'school_blocked',
    'landing',
    'contact',
    'help_page',
    'about',
    'privacy',
    'terms',
    'school_signup',
    'redirect_to_own_dashboard',
}

# URL prefixes always allowed
ALLOWED_PATH_PREFIXES = (
    '/static/',
    '/media/',
    '/admin/login/',
    '/admin/logout/',
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/password/reset/',
    '/accounts/signup/',
    '/school-blocked/',
    '/logout/',
)


class SubscriptionBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Not authenticated → pass
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Super admins always pass
        if getattr(request.user, 'role', None) == 'super_admin':
            return self.get_response(request)

        # Allowed path prefixes
        path = request.path
        if any(path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
            return self.get_response(request)

        # Allowed URL names
        try:
            match = resolve(path)
            if match.url_name in ALLOWED_URL_NAMES:
                return self.get_response(request)
        except Resolver404:
            pass

        # Get user's school
        school = getattr(request.user, 'school', None)

        # No school → pass (super_admin handled above)
        if school is None:
            return self.get_response(request)

        # School inactive → redirect to blocked page (ONCE)
        if not school.is_active:
            blocked_url = reverse('school_blocked')
            if path != blocked_url:
                return redirect(blocked_url)
            # Already on blocked page → let it render
            return self.get_response(request)

        return self.get_response(request)