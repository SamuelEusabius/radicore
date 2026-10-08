"""
School Tenant Middleware.

Attaches request.school based on:
1. Subdomain (e.g. nairobi.yourschool.com)
2. Logged-in user's school

IMPORTANT: This middleware NEVER redirects. It only attaches data.
Redirects cause infinite loops when combined with auth views.
"""

from .models import School


class SchoolTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.school = None

        # Try subdomain-based resolution
        try:
            host = request.get_host().split(':')[0]
            parts = host.split('.')
            if len(parts) > 2 and parts[0] not in ('www', 'localhost'):
                request.school = School.objects.filter(
                    slug=parts[0], is_active=True
                ).first()
        except Exception:
            pass

        # Fallback to the logged-in user's school
        if request.school is None and hasattr(request, 'user'):
            if request.user.is_authenticated:
                request.school = getattr(request.user, 'school', None)

        return self.get_response(request)