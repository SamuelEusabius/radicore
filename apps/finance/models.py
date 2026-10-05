from django.db import models
from django.utils import timezone
from .wallet_models import StudentWallet, WalletTransaction


# ==========================================================
# FEE STRUCTURE — Defines fees per class per term
# ==========================================================

class FeeStructure(models.Model):
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='fee_structures'
    )
    name = models.CharField(max_length=100)
    class_level = models.CharField(max_length=50)
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.class_level} (KES {self.amount_kes})"


# ==========================================================
# INVOICE — Individual student fee invoice
# ==========================================================

class Invoice(models.Model):
    class Status(models.TextChoices):
        UNPAID  = 'unpaid',  'Unpaid'
        PARTIAL = 'partial', 'Partially Paid'
        PAID    = 'paid',    'Paid'
        OVERDUE = 'overdue', 'Overdue'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        related_name='invoices'
    )
    fee_structure = models.ForeignKey(
        FeeStructure, on_delete=models.PROTECT,
        related_name='invoices'
    )
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.UNPAID
    )
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice #{self.id} — {self.student} (KES {self.balance})"

    @property
    def balance(self):
        return self.amount_due - self.amount_paid

    def update_status(self):
        if self.amount_paid >= self.amount_due:
            self.status = self.Status.PAID
        elif self.amount_paid > 0:
            self.status = self.Status.PARTIAL
        elif self.due_date < timezone.now().date():
            self.status = self.Status.OVERDUE
        else:
            self.status = self.Status.UNPAID
        self.save(update_fields=['status'])


# ==========================================================
# PAYMENT — A payment made against an invoice
# ==========================================================

class Payment(models.Model):
    class Method(models.TextChoices):
        MPESA  = 'mpesa',  'M-Pesa'
        AIRTEL = 'airtel', 'Airtel Money'
        STRIPE = 'stripe', 'Stripe'
        CASH   = 'cash',   'Cash'
        BANK   = 'bank',   'Bank Transfer'
        CHEQUE = 'cheque', 'Cheque'

    # Method prefix codes (2 letters)
    METHOD_PREFIX = {
        'mpesa':  'MP',
        'airtel': 'AT',
        'bank':   'BK',
        'cash':   'CS',
        'cheque': 'CQ',
        'stripe': 'ST',
    }

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE,
        related_name='payments'
    )
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices)
    reference = models.CharField(
        max_length=100, unique=True, db_index=True,
        help_text="Auto-generated internal reference"
    )
    external_reference = models.CharField(
        max_length=100, blank=True, default='',
        help_text="M-Pesa receipt, bank slip, cheque number, etc."
    )
    paid_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f"{self.reference} — KES {self.amount_kes}"

    def save(self, *args, **kwargs):
        # Auto-generate reference if blank
        if not self.reference:
            self.reference = self.generate_reference(self.method)

        super().save(*args, **kwargs)

        # Update invoice totals
        self.invoice.amount_paid = sum(
            p.amount_kes for p in self.invoice.payments.all()
        )
        self.invoice.update_status()

    @staticmethod
    def generate_reference(method):
        """
        Generate a unique 10-character reference number.

        Format: <PREFIX><8-DIGIT-SEQUENCE>
        Example: MP00000001, BK00000045, CS00000123

        Uses a per-method sequence to guarantee uniqueness forever.
        Falls back to random suffix on collision.
        """
        import random
        import string
        from django.db import transaction

        prefix = Payment.METHOD_PREFIX.get(method, 'TXN')

        with transaction.atomic():
            # Get all refs with this prefix matching the 8-digit pattern
            refs = Payment.objects.filter(
                reference__startswith=prefix,
            ).values_list('reference', flat=True)

            # Extract highest number
            max_num = 0
            for ref in refs:
                # Strip prefix, check if remaining is digits
                suffix = ref[len(prefix):]
                if suffix.isdigit() and len(suffix) >= 8:
                    try:
                        num = int(suffix)
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue

            next_num = max_num + 1

            # Format with 8 digits, or 9 if exceeded
            if next_num <= 99999999:
                ref = f"{prefix}{next_num:08d}"
            elif next_num <= 999999999:
                ref = f"{prefix}{next_num:09d}"
            else:
                ref = None

            # Fallback to random if sequence exhausted or collision
            if not ref or Payment.objects.filter(reference=ref).exists():
                for _ in range(10):
                    suffix = ''.join(
                        random.choices(string.ascii_uppercase + string.digits, k=8)
                    )
                    candidate = f"{prefix}{suffix}"
                    if not Payment.objects.filter(reference=candidate).exists():
                        return candidate
                raise RuntimeError(
                    'Could not generate unique reference — please try again'
                )

            return ref

    @property
    def method_badge(self):
        return {
            'mpesa':  ('M-Pesa', '#00a651', '#fff'),
            'airtel': ('Airtel', '#e60000', '#fff'),
            'bank':   ('Bank', '#1a237e', '#fff'),
            'cash':   ('Cash', '#059669', '#fff'),
            'cheque': ('Cheque', '#7c3aed', '#fff'),
            'stripe': ('Stripe', '#635bff', '#fff'),
        }.get(self.method, ('Other', '#6b7280', '#fff'))


# ==========================================================
# EXPENDITURE — School expenses
# ==========================================================

class Expenditure(models.Model):
    """School expenditure — salaries, food, utilities, transport, etc."""

    class Category(models.TextChoices):
        SALARIES    = 'salaries',    'Salaries & Wages'
        FOOD        = 'food',        'Food & Kitchen'
        UTILITIES   = 'utilities',   'Utilities (Water, Electricity)'
        TRANSPORT   = 'transport',   'Transport & Fuel'
        MAINTENANCE = 'maintenance', 'Maintenance & Repairs'
        SUPPLIES    = 'supplies',    'Supplies & Stationery'
        RENT        = 'rent',        'Rent & Lease'
        EVENTS      = 'events',      'Events & Activities'
        OTHER       = 'other',       'Other'

    class PayMethod(models.TextChoices):
        CASH   = 'cash',   'Cash'
        MPESA  = 'mpesa',  'M-Pesa'
        BANK   = 'bank',   'Bank Transfer'
        CHEQUE = 'cheque', 'Cheque'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='expenditures'
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=200)
    amount_kes = models.DecimalField(max_digits=12, decimal_places=2)
    spent_on = models.DateField()
    paid_to = models.CharField(max_length=100, blank=True, default='')
    payment_method = models.CharField(
        max_length=20, choices=PayMethod.choices, default=PayMethod.CASH
    )
    reference = models.CharField(max_length=100, blank=True, default='')
    recorded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-spent_on', '-created_at']

    def __str__(self):
        return f"{self.description} — KES {self.amount_kes}"