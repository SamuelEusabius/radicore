"""
Test STK Push from the terminal.

Usage:
    python manage.py test_mpesa_stk +254708374149 1 100
"""
from django.core.management.base import BaseCommand
from apps.finance.services import mpesa as mpesa_service
from apps.finance.mpesa_models import MpesaTransaction
from apps.finance.models import Invoice


class Command(BaseCommand):
    help = "Test M-Pesa STK Push via Daraja API"

    def add_arguments(self, parser):
        parser.add_argument('phone', type=str, help='Phone (e.g. +254708374149)')
        parser.add_argument('invoice_id', type=int, help='Invoice ID to pay')
        parser.add_argument('amount', type=float, help='Amount in KES')

    def handle(self, *args, **options):
        phone = options['phone']
        invoice_id = options['invoice_id']
        amount = options['amount']

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== M-Pesa STK Push Test ==='))
        self.stdout.write(f"Phone:      {phone}")
        self.stdout.write(f"Invoice ID: {invoice_id}")
        self.stdout.write(f"Amount:     KES {amount}")

        invoice = Invoice.objects.filter(id=invoice_id).first()
        if not invoice:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Invoice #{invoice_id} not found — testing without DB record"
            ))
        else:
            self.stdout.write(f"Student:    {invoice.student.full_name}")
            self.stdout.write(f"Balance:    KES {invoice.balance}")

        self.stdout.write('\nCalling Safaricom...\n')

        try:
            result = mpesa_service.stk_push(
                phone=phone,
                amount=amount,
                account_reference=f"INV{invoice_id}",
                description="Test STK Push",
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ API Error: {e}"))
            return

        # Save transaction log
        if invoice:
            MpesaTransaction.objects.create(
                school=invoice.student.school,
                invoice=invoice,
                phone=mpesa_service.normalize_phone(phone),
                amount=amount,
                merchant_request_id=result.get('MerchantRequestID', ''),
                checkout_request_id=result.get('CheckoutRequestID', ''),
                raw_callback=result,
            )

        self.stdout.write(self.style.SUCCESS('\n✅ Response from Safaricom:'))
        for k, v in result.items():
            self.stdout.write(f"  {k}: {v}")

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Next Steps ==='))
        self.stdout.write("1. Check your phone for the STK Push prompt")
        self.stdout.write("2. Enter your M-Pesa PIN")
        self.stdout.write("3. Safaricom will POST to your callback URL")
        self.stdout.write("4. Check MpesaTransaction in admin for result")
        self.stdout.write('')