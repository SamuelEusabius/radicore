"""
M-Pesa transaction tracking models.

Every STK Push and C2B payment attempt is logged here for:
  - Audit trail
  - Reconciliation
  - Debugging failed payments
  - Preventing duplicate processing
"""
from django.db import models


class MpesaTransaction(models.Model):
    """A single M-Pesa transaction attempt (STK Push or C2B)."""

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        SUCCESS  = 'success',  'Success'
        FAILED   = 'failed',   'Failed'
        CANCELLED= 'cancelled','Cancelled by user'
        TIMEOUT  = 'timeout',  'Timed out'

    class Type(models.TextChoices):
        STK_PUSH = 'stk_push', 'STK Push'
        C2B      = 'c2b',      'C2B (Paybill)'


    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='mpesa_transactions',
        null=True, blank=True,
    )
    invoice = models.ForeignKey(
        'finance.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mpesa_transactions',
    )
    payment = models.OneToOneField(
        'finance.Payment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mpesa_transaction',
    )

    transaction_type = models.CharField(
        max_length=10, choices=Type.choices, default=Type.STK_PUSH
    )

    phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Safaricom IDs
    merchant_request_id = models.CharField(
        max_length=100, blank=True, default='', db_index=True
    )
    checkout_request_id = models.CharField(
        max_length=100, blank=True, default='', db_index=True
    )
    mpesa_receipt_number = models.CharField(
        max_length=50, blank=True, default='', db_index=True,
        help_text="Populated on success. Unique per transaction."
    )

    # Result
    result_code = models.IntegerField(null=True, blank=True)
    result_description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    # Raw audit
    raw_request = models.JSONField(default=dict, blank=True)
    raw_callback = models.JSONField(default=dict, blank=True)

    initiated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mpesa_initiated'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['mpesa_receipt_number']),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} — {self.phone} — KES {self.amount} ({self.get_status_display()})"

    @property
    def is_successful(self):
        return self.status == self.Status.SUCCESS

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING