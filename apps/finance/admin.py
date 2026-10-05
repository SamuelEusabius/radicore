from django.contrib import admin
from .models import FeeStructure, Invoice, Payment
from .mpesa_models import MpesaTransaction
from .wallet_models import StudentWallet, WalletTransaction
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
    

# ============================================================
# STUDENT WALLET
# ============================================================

@admin.register(StudentWallet)
class StudentWalletAdmin(admin.ModelAdmin):
    list_display = ('student', 'school', 'balance', 'is_locked', 'daily_withdrawal_limit', 'updated_at')
    list_filter = ('school', 'is_locked')
    search_fields = ('student__first_name', 'student__last_name', 'student__admission_number')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'wallet', 'tx_type', 'source', 'amount', 'balance_after', 'status', 'created_at')
    list_filter = ('tx_type', 'source', 'status', 'created_at')
    search_fields = ('reference', 'wallet__student__first_name', 'wallet__student__last_name', 'external_reference')
    date_hierarchy = 'created_at'