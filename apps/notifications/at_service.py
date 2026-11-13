"""
Africa's Talking SMS Service
- BYOS (Bring Your Own SMS) model
- Auto-formats Kenyan phone numbers
- Logs every SMS in SMSMessageLog
"""
import africastalking
from django.utils import timezone


def format_kenyan_phone(phone):
    """Convert 0712..., 254712..., 712... → +254712..."""
    phone = str(phone).strip().replace(' ', '').replace('-', '')
    if phone.startswith('+254'):
        return phone
    if phone.startswith('254'):
        return '+' + phone
    if phone.startswith('0'):
        return '+254' + phone[1:]
    if len(phone) == 9:
        return '+254' + phone
    return phone


def send_sms(school, phone_number, message, user=None):
    """
    Send an SMS using the school's Africa's Talking credentials.
    Falls back to platform config if the school has none.

    Returns: (success: bool, status_string: str)
    """
    from apps.notifications.models import (
        SchoolSMSConfig, PlatformSMSConfig, SMSMessageLog
    )

    phone = format_kenyan_phone(phone_number)

    # 1. Pick the right config
    config = None
    school_for_log = school
    if school:
        try:
            config = SchoolSMSConfig.objects.get(school=school, is_active=True)
        except SchoolSMSConfig.DoesNotExist:
            config = None

    if not config:
        config = PlatformSMSConfig.objects.filter(is_active=True).first()
        school_for_log = None  # Platform sent it

    if not config:
        return False, "No SMS configuration found (neither school nor platform)."

    # 2. Send via Africa's Talking
    try:
        africastalking.initialize(config.username, config.api_key)
        sms = africastalking.SMS
        response = sms.send(message, [phone], sender_id=config.sender_id)

        # 3. Parse response
        status = "Unknown"
        cost = None
        if response and 'SMSMessageData' in response:
            recipients = response['SMSMessageData'].get('Recipients', [])
            if recipients:
                status = recipients[0].get('status', 'Unknown')
                cost = recipients[0].get('cost')

        # 4. Log it
        SMSMessageLog.objects.create(
            school=school_for_log,
            user=user,
            phone_number=phone,
            message=message,
            status='sent' if status in ['Success', 'Sent'] else 'failed',
            provider_status=status,
            response_data=response,
            cost=cost,
        )

        is_ok = status in ['Success', 'Sent']
        return is_ok, status

    except Exception as e:
        SMSMessageLog.objects.create(
            school=school_for_log,
            user=user,
            phone_number=phone,
            message=message,
            status='failed',
            provider_status='Exception',
            response_data={'error': str(e)},
        )
        return False, str(e)


def fetch_balance(school=None):
    """Fetch current SMS credit balance from Africa's Talking."""
    from apps.notifications.models import SchoolSMSConfig, PlatformSMSConfig

    config = None
    if school:
        try:
            config = SchoolSMSConfig.objects.get(school=school, is_active=True)
        except SchoolSMSConfig.DoesNotExist:
            pass
    if not config:
        config = PlatformSMSConfig.objects.filter(is_active=True).first()

    if not config:
        return None

    try:
        africastalking.initialize(config.username, config.api_key)
        application = africastalking.Application
        response = application.fetch_application_data()
        balance = response.get('UserData', {}).get('balance', 'KES 0.0000')

        # Extract numeric value
        numeric = float(balance.replace('KES', '').strip())

        # Cache it
        if school and hasattr(school, 'sms_config'):
            school.sms_config.cached_balance = numeric
            school.sms_config.last_balance_check = timezone.now()
            school.sms_config.save()

        return balance
    except Exception as e:
        return f"Error: {e}"