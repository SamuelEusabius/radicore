"""
Student Wallet — preloaded money that students can withdraw for
shopping, fare, snacks, etc.

Funds are loaded by parents via M-Pesa (or manually by accountant),
then withdrawn either:
  - Directly at the accountant's office (student)
  - Via the class teacher (who hands cash to the student)

Every deposit and withdrawal is recorded with full audit trail.
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone


class StudentWallet(models.Model):
    """One wallet per student. Tracks running balance."""

    student = models.OneToOneField(
        'students.Student', on_delete=models.CASCADE,
        related_name='wallet'
    )
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='student_wallets'
    )

    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )

    # Controls
    is_locked = models.BooleanField(
        default=False, help_text="Lock wallet (no withdrawals allowed)"
    )
    daily_withdrawal_limit = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('500.00'),
        help_text="Max amount student can withdraw per day"
    )
    minimum_balance = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        help_text="Balance cannot drop below this"
    )

    locked_reason = models.CharField(max_length=200, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__class_level', 'student__first_name']

    def __str__(self):
        return f"{self.student.full_name} — KES {self.balance}"

    @property
    def student_name(self):
        return self.student.full_name

    @property
    def is_low(self):
        return self.balance < 100

    @property
    def today_withdrawn(self):
        """Total withdrawn today (completed + pending)."""
        today = timezone.now().date()
        qs = self.transactions.filter(
            tx_type='withdrawal',
            created_at__date=today,
            status__in=['completed', 'pending_collection', 'collected'],
        )
        return sum(t.amount for t in qs)

    @property
    def can_withdraw_today(self):
        return self.today_withdrawn < self.daily_withdrawal_limit


class WalletTransaction(models.Model):
    """A single wallet transaction — deposit or withdrawal."""

    class TxType(models.TextChoices):
        DEPOSIT    = 'deposit',    'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        REVERSAL   = 'reversal',   'Reversal'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    class Source(models.TextChoices):
        MPESA       = 'mpesa',       'M-Pesa (Parent)'
        CASH        = 'cash',        'Cash (At School)'
        BANK        = 'bank',        'Bank Transfer'
        MANUAL      = 'manual',      'Manual (Admin)'
        SCHOOL_FEE  = 'school_fee',  'School Fee Refund'
        SHOP        = 'shop',        'Shop Purchase'
        OTHER       = 'other',       'Other'

    class Status(models.TextChoices):
        COMPLETED          = 'completed',          'Completed'
        PENDING_COLLECTION = 'pending_collection', 'Pending Collection'
        COLLECTED          = 'collected',          'Collected'
        CANCELLED          = 'cancelled',          'Cancelled'
        FAILED             = 'failed',             'Failed'

    wallet = models.ForeignKey(
        StudentWallet, on_delete=models.CASCADE,
        related_name='transactions'
    )

    tx_type = models.CharField(max_length=15, choices=TxType.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.COMPLETED)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)

    # External reference (M-Pesa code, receipt #, etc.)
    reference = models.CharField(max_length=100, blank=True, default='')
    external_reference = models.CharField(max_length=100, blank=True, default='')

    # Who did it
    initiated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='wallet_transactions_initiated'
    )

    # Withdrawal-specific
    withdrawn_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='wallet_withdrawals'
    )
    collected_by_name = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Who physically received the cash (usually student)"
    )
    collected_at = models.DateTimeField(null=True, blank=True)

    purpose = models.CharField(
        max_length=200, blank=True, default='',
        help_text="e.g. Shopping, Fare, Snacks"
    )

    notes = models.TextField(blank=True, default='')

    # Link to M-Pesa transaction if applicable
    mpesa_transaction = models.OneToOneField(
        'finance.MpesaTransaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='wallet_transaction'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['tx_type', 'status']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        sign = '+' if self.tx_type == self.TxType.DEPOSIT else '-'
        return f"{sign}KES {self.amount} ({self.wallet.student.full_name})"

    @property
    def is_credit(self):
        return self.tx_type in (self.TxType.DEPOSIT, self.TxType.REVERSAL)

    @property
    def is_debit(self):
        return self.tx_type in (self.TxType.WITHDRAWAL,)

    def save(self, *args, **kwargs):
        # Auto-generate reference if not set
        if not self.reference:
            import random
            import string
            prefix = 'WD' if self.tx_type == self.TxType.WITHDRAWAL else 'DP'
            code = ''.join(random.choices(string.digits, k=6))
            self.reference = f"{prefix}-{self.wallet.student.admission_number}-{code}"
        super().save(*args, **kwargs)