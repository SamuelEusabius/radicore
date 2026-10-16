"""
Secretary services — SMS notifications and helpers.
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_sms(phone: str, message: str) -> dict:
    """Internal helper — never raises."""
    try:
        from apps.notifications.services.sms import send_sms
        return send_sms(phone, message)
    except Exception as e:
        logger.exception("SMS failed: %s", e)
        return {'success': False, 'message': str(e)}


def notify_host_of_appointment(appointment) -> dict:
    """SMS the host when a new appointment is booked."""
    if not appointment.host_user or not appointment.host_user.phone:
        return {'success': False, 'message': 'Host has no phone'}

    msg = (
        f"{appointment.school.name}: New appointment booked — "
        f"{appointment.requester_name} on "
        f"{appointment.scheduled_date:%d %b} at "
        f"{appointment.scheduled_time:%H:%M}. "
        f"Subject: {appointment.subject}"
    )
    return _send_sms(appointment.host_user.phone, msg)


def notify_requester_appointment_confirmed(appointment) -> dict:
    """SMS the requester when their appointment is confirmed."""
    if not appointment.requester_phone:
        return {'success': False, 'message': 'Requester has no phone'}

    msg = (
        f"{appointment.school.name}: Your appointment is confirmed for "
        f"{appointment.scheduled_date:%d %b} at "
        f"{appointment.scheduled_time:%H:%M} "
        f"with {appointment.host_display}."
    )
    return _send_sms(appointment.requester_phone, msg)


def notify_requester_appointment_cancelled(appointment) -> dict:
    """SMS the requester when their appointment is cancelled."""
    if not appointment.requester_phone:
        return {'success': False, 'message': 'Requester has no phone'}

    msg = (
        f"{appointment.school.name}: Your appointment scheduled for "
        f"{appointment.scheduled_date:%d %b} at "
        f"{appointment.scheduled_time:%H:%M} has been cancelled. "
        f"Please call the office to reschedule."
    )
    return _send_sms(appointment.requester_phone, msg)


def notify_guardian_application_received(application) -> dict:
    """SMS guardian when an admission application is received."""
    if not application.guardian_phone:
        return {'success': False, 'message': 'No guardian phone'}

    msg = (
        f"{application.school.name}: Application received for "
        f"{application.full_name} — Ref {application.reference_number}. "
        f"We will contact you shortly."
    )
    return _send_sms(application.guardian_phone, msg)


def notify_guardian_application_status(application) -> dict:
    """SMS guardian when an application status changes."""
    if not application.guardian_phone:
        return {'success': False, 'message': 'No guardian phone'}

    msg = (
        f"{application.school.name}: Application {application.reference_number} "
        f"for {application.full_name} — status: {application.get_status_display()}."
    )
    return _send_sms(application.guardian_phone, msg)


# ==========================================================
# Cross-module helpers (from CSO module)
# ==========================================================

def notify_admin_official_visitor(visitor) -> dict:
    """
    SMS the admin host when an OFFICIAL visitor's pass is issued by Secretary.
    Called from secretary_official_issue_pass view.
    """
    host = visitor.host_user
    if not host or not host.phone:
        return {'success': False, 'message': 'Admin host has no phone'}

    msg = (
        f"{visitor.school.name}: OFFICIAL visitor awaiting you — "
        f"{visitor.full_name}"
        f"{' from ' + visitor.organisation if visitor.organisation else ''}. "
        f"Official pass issued at reception. Please sign when receiving."
    )
    return _send_sms(host.phone, msg)