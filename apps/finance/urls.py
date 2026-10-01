from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FeeStructureViewSet,
    InvoiceViewSet,
    mpesa_callback,
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
    path('receipt/<int:payment_id>/pdf/',
         receipt_pdf,
         name='receipt_pdf'),

    path('statement/<int:student_id>/pdf/',
         fee_statement_pdf,
         name='fee_statement_pdf'),

    # ==========================================================
    # M-PESA — Legacy callback (kept for compatibility)
    # ==========================================================
    path('mpesa/callback/',
         mpesa_callback,
         name='mpesa_callback'),

    # ==========================================================
    # M-PESA — New endpoints (from mpesa_views)
    # ==========================================================
    path('mpesa/stk-push/<int:invoice_id>/',
         mpesa_views.mpesa_stk_push,
         name='mpesa_stk_push'),

    path('mpesa/status/<str:checkout_request_id>/',
         mpesa_views.mpesa_status,
         name='mpesa_status'),

    path('mpesa/c2b/validation/',
         mpesa_views.mpesa_c2b_validation,
         name='mpesa_c2b_validation'),

    path('mpesa/c2b/confirmation/',
         mpesa_views.mpesa_c2b_confirmation,
         name='mpesa_c2b_confirmation'),
]