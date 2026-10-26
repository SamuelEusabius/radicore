from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FeeStructureViewSet,
    InvoiceViewSet,
    receipt_pdf,
    fee_statement_pdf,
)
from . import mpesa_views


router = DefaultRouter()
router.register('fee-structures', FeeStructureViewSet, basename='fee-structure')
router.register('invoices', InvoiceViewSet, basename='invoice')


urlpatterns = router.urls + [
    # ==========================================================
    # PDFs
    # ==========================================================
    path('receipt/<int:payment_id>/pdf/', receipt_pdf, name='receipt_pdf'),
    path('statement/<int:student_id>/pdf/', fee_statement_pdf, name='fee_statement_pdf'),

    # ==========================================================
    # M-PESA — Accountant Dashboard Views
    # ==========================================================
    path('mpesa/ledger/', mpesa_views.accountant_mpesa_ledger, name='accountant_mpesa_ledger'),
    path('mpesa/manual/', mpesa_views.accountant_manual_mpesa, name='accountant_manual_mpesa'),
    path('mpesa/settings/', mpesa_views.accountant_mpesa_settings, name='accountant_mpesa_settings'),

    # ==========================================================
    # M-PESA — Safaricom Callbacks
    # ==========================================================
    # This is the URL the accountant copies into the Safaricom Daraja Portal.
    path('mpesa/c2b/confirmation/', mpesa_views.mpesa_c2b_confirmation, name='mpesa_c2b_confirmation'),
    
    # We alias the legacy callback URL to the new one so existing configurations don't break.
    path('mpesa/callback/', mpesa_views.mpesa_c2b_confirmation, name='mpesa_callback'),
    path('mpesa/platform-callback/', mpesa_views.platform_c2b_confirmation, name='platform_c2b_confirmation'),
]
