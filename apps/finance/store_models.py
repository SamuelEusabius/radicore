"""
Store Keeper module — inventory, suppliers, stock movements.

Handles:
  - Supplier management
  - Item catalogue
  - Stock receiving (from suppliers)
  - Stock issuing (to students, staff, departments)
  - Returns
  - Full audit trail of every movement
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone


# ============================================================
# SUPPLIERS
# ============================================================

class Supplier(models.Model):
    """A vendor that supplies items to the school."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='suppliers'
    )
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.CharField(max_length=300, blank=True, default='')
    kra_pin = models.CharField(max_length=30, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('school', 'name')

    def __str__(self):
        return self.name


# ============================================================
# ITEM CATEGORIES
# ============================================================

class ItemCategory(models.Model):
    """Categories for grouping items (e.g. Stationery, Cleaning)."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='item_categories'
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        ordering = ['name']
        unique_together = ('school', 'name')
        verbose_name_plural = 'Item Categories'

    def __str__(self):
        return self.name


# ============================================================
# INVENTORY ITEMS
# ============================================================

class InventoryItem(models.Model):
    """An item in the school store."""

    UNIT_CHOICES = [
        ('piece', 'Pieces'),
        ('ream', 'Reams'),
        ('box', 'Boxes'),
        ('packet', 'Packets'),
        ('kg', 'Kilograms'),
        ('litre', 'Litres'),
        ('roll', 'Rolls'),
        ('set', 'Sets'),
        ('other', 'Other'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='inventory_items'
    )
    category = models.ForeignKey(
        ItemCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='items'
    )
    code = models.CharField(max_length=50, blank=True, default='')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='piece')

    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Current stock"
    )
    min_stock = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('5.00'),
        help_text="Alert when stock drops below this"
    )
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Average cost per unit"
    )

    storage_location = models.CharField(
        max_length=100, blank=True, default='',
        help_text="e.g. Shelf A3, Store Room 2"
    )
    primary_supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='items_supplied'
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__name', 'name']
        unique_together = ('school', 'name')
        indexes = [
            models.Index(fields=['school', 'is_active']),
            models.Index(fields=['school', 'category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.get_unit_display()})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_stock

    @property
    def is_out_of_stock(self):
        return self.quantity <= 0

    @property
    def total_value(self):
        return self.quantity * self.unit_cost


# ============================================================
# STOCK RECEIPTS (Stock In)
# ============================================================

class StockReceipt(models.Model):
    """A record of stock received from a supplier."""
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='stock_receipts'
    )
    receipt_number = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text="Auto-generated internal reference"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='receipts'
    )
    supplier_invoice_no = models.CharField(
        max_length=100, blank=True, default='',
        help_text="Supplier's own invoice/reference number"
    )
    received_date = models.DateField(default=timezone.now)
    received_time = models.TimeField(auto_now_add=True)

    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    notes = models.TextField(blank=True, default='')

    received_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='stock_receipts'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_date', '-received_time']
        indexes = [models.Index(fields=['school', '-received_date'])]

    def __str__(self):
        return f"{self.receipt_number} — {self.supplier.name if self.supplier else 'No supplier'}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import random
            import string
            from django.db import transaction
            code = ''.join(random.choices(string.digits, k=6))
            self.receipt_number = f"RC-{timezone.now().strftime('%Y%m%d')}-{code}"
        super().save(*args, **kwargs)


class StockReceiptItem(models.Model):
    """One line item inside a stock receipt."""
    receipt = models.ForeignKey(
        StockReceipt, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='receipt_lines'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_cost
        super().save(*args, **kwargs)


# ============================================================
# STOCK ISSUES (Stock Out)
# ============================================================

class StockIssue(models.Model):
    """A record of items issued to a recipient."""

    RECIPIENT_TYPE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('trainer', 'Trainer'),
        ('staff', 'Support Staff'),
        ('department', 'Department'),
        ('boarding', 'Boarding Section'),
        ('admin', 'Administration'),
        ('other', 'Other'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='stock_issues'
    )
    issue_number = models.CharField(
        max_length=50, unique=True, db_index=True,
        help_text="Auto-generated internal reference"
    )

    recipient_type = models.CharField(
        max_length=20, choices=RECIPIENT_TYPE_CHOICES, default='department'
    )
    recipient_student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_issues'
    )
    recipient_user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_issues_received'
    )
    recipient_department = models.CharField(
        max_length=150, blank=True, default='',
        help_text="Free text if department or other"
    )
    recipient_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Who physically received the item"
    )

    purpose = models.CharField(
        max_length=200, blank=True, default='',
        help_text="e.g. Class supplies, Maintenance, Uniform"
    )

    issued_date = models.DateField(default=timezone.now)
    issued_time = models.TimeField(auto_now_add=True)

    notes = models.TextField(blank=True, default='')

    issued_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='stock_issues_made'
    )
    authorized_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='stock_issues_authorized'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_date', '-issued_time']
        indexes = [models.Index(fields=['school', '-issued_date'])]

    def __str__(self):
        return f"{self.issue_number} → {self.recipient_name or self.recipient_department or '?'}"

    def save(self, *args, **kwargs):
        if not self.issue_number:
            import random
            import string
            code = ''.join(random.choices(string.digits, k=6))
            self.issue_number = f"IS-{timezone.now().strftime('%Y%m%d')}-{code}"
        super().save(*args, **kwargs)

    @property
    def recipient_display(self):
        if self.recipient_student:
            return self.recipient_student.full_name
        if self.recipient_user:
            return self.recipient_user.get_full_name() or self.recipient_user.email
        if self.recipient_department:
            return self.recipient_department
        if self.recipient_name:
            return self.recipient_name
        return '—'


class StockIssueItem(models.Model):
    """One line item inside a stock issue."""
    issue = models.ForeignKey(
        StockIssue, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='issue_lines'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


# ============================================================
# STOCK RETURNS
# ============================================================

class StockReturn(models.Model):
    """A record of items returned to the store."""

    CONDITION_CHOICES = [
        ('good', 'Good — Reusable'),
        ('damaged', 'Damaged'),
        ('expired', 'Expired'),
        ('unusable', 'Unusable'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='stock_returns'
    )
    return_number = models.CharField(
        max_length=50, unique=True, db_index=True
    )

    returned_by_student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_returns'
    )
    returned_by_user = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_returns_made'
    )
    returned_by_name = models.CharField(
        max_length=200, blank=True, default=''
    )

    return_date = models.DateField(default=timezone.now)
    return_time = models.TimeField(auto_now_add=True)

    reason = models.CharField(max_length=200, blank=True, default='')
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default='good'
    )
    notes = models.TextField(blank=True, default='')

    received_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='stock_returns_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-return_date', '-return_time']

    def __str__(self):
        return f"{self.return_number}"

    def save(self, *args, **kwargs):
        if not self.return_number:
            import random
            import string
            code = ''.join(random.choices(string.digits, k=6))
            self.return_number = f"RT-{timezone.now().strftime('%Y%m%d')}-{code}"
        super().save(*args, **kwargs)


class StockReturnItem(models.Model):
    """One line item inside a stock return."""
    stock_return = models.ForeignKey(
        StockReturn, on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT,
        related_name='return_lines'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    condition = models.CharField(max_length=20, default='good')
    notes = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} x {self.quantity}"


# ============================================================
# STOCK MOVEMENT (Unified Audit Trail)
# ============================================================

class StockMovement(models.Model):
    """Every movement of every item — for a unified audit trail."""

    ACTION_CHOICES = [
        ('receipt', 'Received from Supplier'),
        ('issue', 'Issued'),
        ('return', 'Returned'),
        ('adjustment', 'Manual Adjustment'),
        ('loss', 'Loss / Theft'),
    ]

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE,
        related_name='movements'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Positive for in, negative for out"
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    # Links to source document
    receipt = models.ForeignKey(
        StockReceipt, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movements'
    )
    issue = models.ForeignKey(
        StockIssue, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movements'
    )
    stock_return = models.ForeignKey(
        StockReturn, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movements'
    )

    reason = models.CharField(max_length=300, blank=True, default='')
    performed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', '-created_at']),
            models.Index(fields=['item', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.quantity >= 0 else ''
        return f"{sign}{self.quantity} {self.item.name} ({self.get_action_display()})"