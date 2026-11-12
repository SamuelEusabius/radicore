from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse, NoReverseMatch
from django.shortcuts import redirect


class CustomAccountAdapter(DefaultAccountAdapter):
    """Customizes allauth — role-based post-login redirect + 95-char secure session."""

    def get_login_redirect_url(self, request):
        user = request.user
        if not user.is_authenticated:
            return reverse('landing')

        role = getattr(user, 'role', None)

        # Role → URL name mapping
        role_redirects = {
            'super_admin':         'dashboard_home',
            'principal':           'dashboard_home',
            'teacher':             'dashboard_home',
            'accountant':          'dashboard_home',
            'parent':              'dashboard_home',
            'student':             'dashboard_home',
            'driver':              'driver_dashboard',
            'librarian':           'librarian_dashboard',
            'lab_technician':      'lab_technician_dashboard',
            'nurse':               'nurse_dashboard',
            'chief_chef':          'chief_chef_dashboard',
            'director_of_studies': 'dos_dashboard',
            'store_keeper':        'store_keeper_dashboard',
            'boarding_master':     'boarding_dashboard',
            'security_officer':    'cso_dashboard',
            'secretary':           'secretary_dashboard',
        }
        url_name = role_redirects.get(role, 'dashboard_home')

        try:
            return reverse(url_name)
        except NoReverseMatch:
            try:
                return reverse('dashboard_home')
            except NoReverseMatch:
                return '/'

    def login(self, request, user):
        """
        Called by allauth immediately after a successful login.
        Generates a 95-char opaque key, stores its hash, and sets the secure cookie.
        """
        from apps.accounts.models import UserSession
        from django.contrib.auth import login as django_login

        # 1. Let Django mark the user as authenticated (session-based)
        django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        # 2. Generate the 95-char opaque key
        session = UserSession(
            user=user,
            school=user.school,
            ip_address=request.META.get('REMOTE_ADDR'),
            device=request.META.get('HTTP_USER_AGENT', 'Unknown')[:255]
        )
        raw_key = session.generate_key()
        session.save()

        # 3. Store the raw key so we can attach it to the response cookie
        request._rc_raw_session_key = raw_key

    def get_login_response(self, request, user):
        """
        Called after login() to build the HTTP response.
        This is where we inject the HttpOnly cookie with the raw 95-char key.
        """
        response = super().get_login_response(request, user) if hasattr(super(), 'get_login_response') else redirect(self.get_login_redirect_url(request))

        raw_key = getattr(request, '_rc_raw_session_key', None)
        if raw_key:
            response.set_cookie(
                'rc_session_key',
                raw_key,
                httponly=True,
                secure=not request.is_secure() is False,  # Secure in production (DEBUG=False)
                samesite='Lax',
                max_age=60 * 60 * 24 * 30  # 30 days
            )
        return response