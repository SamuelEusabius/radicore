"""
School tenant middleware.

Attaches request.school based on:
  1. Subdomain (e.g. nairobi.elimucore.co.ke)
  2. The logged-in user's own school

SAFETY RULES:
  - If a subdomain resolves to a school, the logged-in user MUST belong to that school.
    Otherwise request.school is set to None and request.tenant_mismatch is True.
  - Falls back to the user's school only when no subdomain school is resolved.
  - Never sets request.school to a school the user is not a member of.

This middleware never redirects. Redirects on mismatch are handled by
TenantMismatchMiddleware in a separate step (view-level, not middleware-level).
"""
import logging

from .models import School

logger = logging.getLogger(__name__)


# Hostname prefixes that are never treated as tenant subdomains
RESERVED_SUBDOMAINS = {
    'www', 'localhost', 'api', 'admin', 'static', 'media', 'app', 'test', 'staging',
}


class SchoolTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.school = None
        request.tenant_mismatch = False
        request.tenant_source = None  # 'subdomain' | 'user' | None

        resolved_from_subdomain = self._resolve_subdomain(request)

        if resolved_from_subdomain is not None:
            request.school = resolved_from_subdomain
            request.tenant_source = 'subdomain'

        # If user is authenticated, enforce membership
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_school = getattr(request.user, 'school', None)

            if request.school is not None and user_school is not None:
                # Subdomain resolved — user must belong to it
                if request.school.id != user_school.id:
                    logger.warning(
                        "Tenant mismatch: user=%s (school=%s) hit subdomain for school=%s",
                        request.user.id, user_school.id, request.school.id,
                    )
                    request.school = None
                    request.tenant_mismatch = True
                    request.tenant_source = None
            elif request.school is None and user_school is not None:
                # No subdomain — fall back to user's school
                request.school = user_school
                request.tenant_source = 'user'

        return self.get_response(request)

    # ---------------- internal ----------------

    def _resolve_subdomain(self, request):
        """Return a School from the subdomain, or None."""
        try:
            host = request.get_host().split(':')[0]
        except Exception:
            return None

        parts = host.split('.')
        if len(parts) < 3:
            return None

        sub = parts[0].lower()
        if sub in RESERVED_SUBDOMAINS:
            return None

        return School.objects.filter(slug=sub, is_active=True).first()