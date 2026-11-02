"""
Management command to send a test SMS via Africa's Talking.

Usage:
    python manage.py send_test_sms +254796174943 "Your test message"
    python manage.py send_test_sms 0796174943 "Your test message"
    python manage.py send_test_sms 0796174943 "Test" --bulk +254711111111 +254722222222
"""
from django.core.management.base import BaseCommand, CommandError
from apps.notifications.services.sms import send_sms, send_bulk_sms, normalize_phone


class Command(BaseCommand):
    help = "Send a test SMS via Africa's Talking (sandbox or production)"

    def add_arguments(self, parser):
        parser.add_argument(
            'phone',
            type=str,
            help='Recipient phone number (e.g. 0796174943 or +254796174943)'
        )
        parser.add_argument(
            'message',
            type=str,
            help='SMS message body'
        )
        parser.add_argument(
            '--bulk',
            nargs='+',
            default=None,
            help='Additional phone numbers for bulk test'
        )

    def handle(self, *args, **options):
        phone = options['phone']
        message = options['message']
        bulk = options.get('bulk')

        normalized = normalize_phone(phone)

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== SMS Test ==='))
        self.stdout.write(f"Original phone:   {phone}")
        self.stdout.write(f"Normalized:       {normalized}")
        self.stdout.write(f"Message:          {message[:80]}{'...' if len(message) > 80 else ''}")
        self.stdout.write(f"Message length:   {len(message)} chars")
        self.stdout.write(f"Bulk extras:      {bulk or 'none'}")
        self.stdout.write('')

        # Single SMS
        if not bulk:
            self.stdout.write('Sending single SMS...')
            result = send_sms(phone, message)
            self._print_result(result)
            return

        # Bulk SMS
        all_phones = [phone] + list(bulk)
        self.stdout.write(f'Sending bulk SMS to {len(all_phones)} numbers...')
        result = send_bulk_sms(all_phones, message)
        self._print_result(result)

    def _print_result(self, result):
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS('\n✅ SENT'))
            recipients = result.get('recipients', [])
            self.stdout.write(f"Recipients returned: {len(recipients)}")
            for r in recipients:
                number = r.get('number', '?')
                status = r.get('status', '?')
                cost = r.get('cost', '?')
                msg_id = r.get('messageId', '?')
                self.stdout.write(f"  → {number} | {status} | {cost} | id={msg_id}")
        else:
            self.stdout.write(self.style.ERROR('\n❌ FAILED'))
            self.stdout.write(f"Reason: {result.get('message', 'unknown')}")

        self.stdout.write('')