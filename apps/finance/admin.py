from django.contrib import admin
from .models import FeeStructure, Invoice, Payment
from .mpesa_models import MpesaTransaction
@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['name', 'class_level', 'amount_kes', 'due_date', 'school']

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'amount_due', 'amount_paid', 'status', 'due_date']
    list_filter = ['status', 'due_date']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'invoice', 'amount_kes', 'method', 'paid_at']
    
    from .mpesa_models import MpesaTransaction


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'transaction_type', 'phone', 'amount',
        'status', 'mpesa_receipt_number', 'created_at'
    )
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = ('phone', 'mpesa_receipt_number',
                     'checkout_request_id', 'merchant_request_id')
    readonly_fields = ('created_at', 'completed_at',
                       'raw_request', 'raw_callback')
    date_hierarchy = 'created_at'