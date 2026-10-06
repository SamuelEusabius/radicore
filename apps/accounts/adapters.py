from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse, NoReverseMatch


class CustomAccountAdapter(DefaultAccountAdapter):
    """Customizes allauth — role-based post-login redirect."""

    def get_login_redirect_url(self, request):
        user = request.user
        if not user.is_authenticated:
            return reverse('landing')

        role = getattr(user, 'role', None)

        # Role → URL name mapping
        role_redirects = {
            'super_admin':         'dashboard_home',
            'school_admin':        'dashboard_home',
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
        }
        url_name = role_redirects.get(role, 'dashboard_home')

        try:
            return reverse(url_name)
        except NoReverseMatch:
            try:
                return reverse('dashboard_home')
            except NoReverseMatch:
                return '/'