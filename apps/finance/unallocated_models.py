"""
Unallocated Payments — M-Pesa payments that couldn't be auto-matched
to a student invoice.

When a parent pays via M-Pesa and the account reference doesn't match
any student, or the amount doesn't fit any outstanding invoice, the
payment is stored here for manual reconciliation.

The bursar can:
  - Reassign to a specific student
  - Split across multiple students (siblings)
  - Create a new invoice to match
  - Transfer to a different school (rare)
  - Refund (edge case)
"""
from decimal import Decimal
from django.db import models


class UnallocatedPayment(models.Model):
    """An M-Pesa payment that hasn't been matched to a student invoice."""

    class Status(models.TextChoices):
        UNALLOCATED = 'unallocated', 'Unallocated'
        ALLOCATED   = 'allocated',   'Allocated'
        TRANSFERRED = 'transferred', 'Transferred to Another Student'
        INVOICED    = 'invoiced',    'Invoice Created'
        REFUNDED    = 'refunded',    'Refunded'
        REJECTED    = 'rejected',    'Rejected (Not Our Payment)'

    # ===== School =====
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='unallocated_payments'
    )

    # ===== M-Pesa Transaction Details =====
    mpesa_receipt = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text="Safaricom receipt number"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone = models.CharField(max_length=15)
    payer_name = models.CharField(max_length=100, blank=True, default='')

    # What the parent typed as the account number
    account_reference = models.CharField(
        max_length=100, blank=True, default='',
        help_text="What parent entered as account (may be wrong)"
    )

    transaction_date = models.DateTimeField()

    # ===== Link to M-Pesa =====
    mpesa_transaction = models.OneToOneField(
        'finance.MpesaTransaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unallocated_payment'
    )

    # ===== Status & Workflow =====
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNALLOCATED
    )

    # ===== Who resolved it =====
    resolved_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unallocated_resolved'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    # ===== Raw callback (full payload for debugging) =====
    raw_callback = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['mpesa_receipt']),
        ]

    def __str__(self):
        return f"{self.mpesa_receipt} — KES {self.amount} ({self.get_status_display()})"

    @property
    def is_resolved(self):
        return self.status != self.Status.UNALLOCATED

    @property
    def age_hours(self):
        """How long has this been unallocated?"""
        from django.utils import timezone
        delta = timezone.now() - self.created_at
        return int(delta.total_seconds() / 3600)


class UnallocatedAllocation(models.Model):
    """How an unallocated payment was allocated to a student's invoice."""

    unallocated_payment = models.ForeignKey(
        UnallocatedPayment, on_delete=models.CASCADE,
        related_name='allocations'
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unallocated_allocations'
    )
    invoice = models.ForeignKey(
        'finance.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unallocated_allocations'
    )
    payment = models.ForeignKey(
        'finance.Payment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='unallocated_allocations'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"KES {self.amount} → {self.student.full_name if self.student else 'N/A'}"