"""
SMS service — Africa's Talking integration for Kenya.
"""

import logging
from django.conf import settings
try:
    import africastalking
    AFRICASTALKING_AVAILABLE = True
except ImportError:
    africastalking = None
    AFRICASTALKING_AVAILABLE = False

logger = logging.getLogger(__name__)


def _initialize():
    """Initialize the Africa's Talking SDK with credentials from settings."""
    if not AFRICASTALKING_AVAILABLE:
        raise RuntimeError(
            "Africa's Talking SDK is not installed. "
            "Run: pip install africastalking"
        )

    username = getattr(settings, 'AT_USERNAME', '') or 'sandbox'
    api_key = getattr(settings, 'AT_API_KEY', '')
    if not api_key:
        raise RuntimeError('AT_API_KEY is not configured in .env')

    africastalking.initialize(username, api_key)
    return africastalking.SMS

def normalize_phone(phone: str) -> str:
    """
    Normalize a Kenyan phone number to E.164 format (+2547XXXXXXXX).
    Accepts: 0712345678, 712345678, 254712345678, +254712345678
    """
    if not phone:
        return ''

    # Strip spaces, dashes, brackets
    p = ''.join(c for c in phone if c.isdigit() or c == '+')

    # Remove leading + if present, we'll re-add
    if p.startswith('+'):
        p = p[1:]

    # Kenyan cases
    if p.startswith('254') and len(p) == 12:
        return f'+{p}'
    if p.startswith('0') and len(p) == 10:
        return f'+254{p[1:]}'
    if len(p) == 9 and (p.startswith('7') or p.startswith('1')):
        return f'+254{p}'

    # Fallback: return as-is with +
    return f'+{p}'


import africastalking
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

import africastalking
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_sms(school, phone_number, message):
    """
    Sends an SMS using the School's specific AT credentials.
    Falls back to the global .env if the school hasn't configured their own.
    """
    if phone_number.startswith('0'):
        phone_number = '+254' + phone_number[1:]
    elif phone_number.startswith('254'):
        phone_number = '+' + phone_number
    elif not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    if hasattr(school, 'sms_config') and school.sms_config.is_active:
        username = school.sms_config.username
        api_key = school.sms_config.api_key
        sender_id = school.sms_config.sender_id
    else:
        username = getattr(settings, 'AT_USERNAME', 'sandbox')
        api_key = getattr(settings, 'AT_API_KEY', '')
        sender_id = getattr(settings, 'AT_SENDER_ID', None)

    try:
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS
        
        response = sms.send(
            message, 
            [phone_number], 
            sender_id=sender_id
        )
        
        # Check if AT actually accepted it
        if response and 'SMSMessageData' in response:
            recipients = response['SMSMessageData'].get('Recipients', [])
            if recipients and recipients[0].get('status') == 'Success':
                return True, response
            else:
                logger.error(f"AT Rejection for {phone_number}: {response}")
                return False, response
                
        return False, "Invalid response from Africa's Talking"

    except Exception as e:
        logger.error(f"SMS Exception for {phone_number} via {school.name}: {str(e)}")
        return False, str(e)
    
    

def send_bulk_sms(phones: list, message: str, sender_id: str = None) -> dict:
    """
    Send the same SMS to many recipients in one API call.
    Africa's Talking supports up to 10,000 recipients per call.

    Args:
        phones: list of phone numbers
        message: SMS text
        sender_id: optional sender ID

    Returns:
        dict: { 'success': bool, 'recipients': list, 'message': str }
    """
    normalized = [normalize_phone(p) for p in phones if p]
    normalized = [p for p in normalized if p]

    if not normalized:
        return {'success': False, 'recipients': [], 'message': 'No valid phone numbers'}

    try:
        SMS = _initialize()

        sender = sender_id or getattr(settings, 'AT_SENDER_ID', '') or None

        if sender:
            response = SMS.send(message, normalized, sender_id=sender)
        else:
            response = SMS.send(message, normalized)

        logger.info(f"Bulk SMS sent to {len(normalized)} recipients")
        return {
            'success': True,
            'recipients': response.get('SMSMessageData', {}).get('Recipients', []),
            'message': f'Sent to {len(normalized)} recipients',
        }

    except Exception as e:
        logger.exception(f"Bulk SMS failed: {e}")
        return {'success': False, 'recipients': [], 'message': str(e)}