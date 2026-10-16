"""
Security / CSO services — SMS notifications and helpers.
"""
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _role_label(role: str) -> str:
    """Human-friendly label for a role code."""
    return {
        'principal':           'Principal',
        'deputy_admin':        'Deputy Principal (Admin)',
        'deputy_academics':    'Deputy Principal (Academics)',
        'director_of_studies': 'Director of Studies',
        'accountant':          'Accountant',
        'boarding_master':     'Boarding Master',
        'secretary':           'Secretary',
    }.get(role, role.replace('_', ' ').title())


def notify_host_of_visitor(visitor) -> dict:
    """
    SMS the host when a visitor arrives to see them.
    Called from visitor_check_in view (CSO).
    """
    try:
        from apps.notifications.services.sms import send_sms
    except ImportError:
        logger.warning("SMS service unavailable")
        return {'success': False, 'message': 'SMS service unavailable'}

    # Resolve host phone
    host_user = visitor.host_user
    if not host_user:
        return {'success': False, 'message': 'No host user; nothing to send'}

    phone = getattr(host_user, 'phone', '') or ''
    if not phone:
        return {'success': False, 'message': 'Host has no phone number'}

    school = visitor.school
    message = (
        f"{school.name}: You have a visitor at the gate — "
        f"{visitor.full_name}"
        f"{' from ' + visitor.organisation if visitor.organisation else ''}. "
        f"Purpose: {visitor.get_purpose_display()}. "
        f"Please come to the reception or send someone."
    )

    return send_sms(phone, message)


def notify_secretary_of_official(visitor) -> dict:
    """
    SMS all secretaries when an OFFICIAL visitor arrives.
    Called from visitor_check_in view (CSO) when visit_type == official.
    """
    try:
        from apps.notifications.services.sms import send_sms
    except ImportError:
        return {'success': False, 'message': 'SMS service unavailable'}

    from apps.accounts.models import User
    from apps.accounts.roles import Role

    school = visitor.school
    secretaries = User.objects.filter(
        school=school, role=Role.SECRETARY
    ).exclude(phone='')

    if not secretaries.exists():
        return {'success': False, 'message': 'No secretaries with phone'}

    host_label = visitor.host_display
    message = (
        f"OFFICIAL VISITOR at gate: {visitor.full_name}"
        f"{' (' + visitor.organisation + ')' if visitor.organisation else ''}. "
        f"To see: {host_label}. "
        f"Please prepare the official pass."
    )

    sent = 0
    for sec in secretaries:
        try:
            result = send_sms(sec.phone, message)
            if result.get('success'):
                sent += 1
        except Exception:
            logger.exception("Failed to notify secretary %s", sec.id)

    return {'success': sent > 0, 'message': f'Notified {sent} secretary(ies)'}


def notify_admin_of_visitor(visitor) -> dict:
    """
    SMS the admin host of an OFFICIAL visitor.
    Called from Secretary's official pass issue view.
    """
    try:
        from apps.notifications.services.sms import send_sms
    except ImportError:
        return {'success': False, 'message': 'SMS service unavailable'}

    host_user = visitor.host_user
    if not host_user:
        return {'success': False, 'message': 'No admin host'}

    phone = getattr(host_user, 'phone', '') or ''
    if not phone:
        return {'success': False, 'message': 'Host has no phone'}

    school = visitor.school
    message = (
        f"{school.name}: OFFICIAL visitor awaiting you — "
        f"{visitor.full_name}"
        f"{' from ' + visitor.organisation if visitor.organisation else ''}. "
        f"Official pass has been issued at reception. "
        f"Please sign the pass when you receive them."
    )
    return send_sms(phone, message)