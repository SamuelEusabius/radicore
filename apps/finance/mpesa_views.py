"""
M-Pesa payment views.

Public endpoints (called by Safaricom):
  - mpesa_callback
  - mpesa_c2b_validation
  - mpesa_c2b_confirmation

Private endpoints (called by our frontend):
  - mpesa_stk_push (parent clicks "Pay Now")
  - mpesa_status (poll for result)
"""
import logging
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.finance.models import Invoice, Payment
from apps.finance.mpesa_models import MpesaTransaction
from apps.finance.services import mpesa as mpesa_service

logger = logging.getLogger(__name__)


# ==========================================================
# STK PUSH — INITIATE (Parent clicks "Pay Now")
# ==========================================================

@login_required
@require_POST
def mpesa_stk_push(request, invoice_id):
    """
    Initiate an STK Push for a given invoice.

    POST params:
        phone (optional) — defaults to parent's phone
        amount (optional) — defaults to invoice balance

    Returns JSON with checkout_request_id for status polling.
    """
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        student__school=request.user.school,
    )

    # Authorization: parent can only pay own children
    if request.user.role == 'parent':
        try:
            request.user.parent_profile.students.get(id=invoice.student_id)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    # Amount
    amount = request.POST.get('amount', '').strip()
    if amount:
        try:
            amount = Decimal(amount)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid amount'}, status=400)
    else:
        amount = invoice.balance

    if amount <= 0:
        return JsonResponse({'success': False, 'error': 'Invoice already paid'}, status=400)

    # Phone
    phone = request.POST.get('phone', '').strip()
    if not phone:
        # Try parent phone
        try:
            phone = request.user.parent_profile.phone
        except Exception:
            phone = ''

    if not phone:
        return JsonResponse({'success': False, 'error': 'Phone number required'}, status=400)

    # Create transaction record
    txn = MpesaTransaction.objects.create(
        school=invoice.student.school,
        invoice=invoice,
        transaction_type=MpesaTransaction.Type.STK_PUSH,
        phone=mpesa_service.normalize_phone(phone),
        amount=amount,
        initiated_by=request.user,
        raw_request={'invoice_id': invoice.id, 'amount': str(amount), 'phone': phone},
    )

    # Call Safaricom
    try:
        result = mpesa_service.stk_push(
            phone=phone,
            amount=float(amount),
            account_reference=f"INV{invoice.id}",
            description=f"Fees - {invoice.student.full_name}",
        )
    except Exception as e:
        logger.exception("STK Push failed")
        txn.status = MpesaTransaction.Status.FAILED
        txn.result_description = str(e)
        txn.save(update_fields=['status', 'result_description'])
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Save Safaricom IDs
    txn.merchant_request_id = result.get('MerchantRequestID', '')
    txn.checkout_request_id = result.get('CheckoutRequestID', '')
    txn.raw_callback = result
    txn.save(update_fields=['merchant_request_id', 'checkout_request_id', 'raw_callback'])

    if result.get('ResponseCode') != '0':
        txn.status = MpesaTransaction.Status.FAILED
        txn.result_description = result.get('ResponseDescription', 'Failed')
        txn.save(update_fields=['status', 'result_description'])

    return JsonResponse({
        'success': True,
        'checkout_request_id': txn.checkout_request_id,
        'message': result.get('CustomerMessage', 'Check your phone to complete payment'),
    })


# ==========================================================
# CALLBACK — SAFARICOM NOTIFIES US (public)
# ==========================================================

@csrf_exempt
@require_POST
def mpesa_callback(request):
    """
    Safaricom calls this URL when an STK Push completes or fails.

    Payload (success):
        {
          "Body": {
            "stkCallback": {
              "MerchantRequestID": "...",
              "CheckoutRequestID": "...",
              "ResultCode": 0,
              "ResultDesc": "The service request is processed successfully.",
              "CallbackMetadata": {
                "Item": [
                  {"Name": "Amount", "Value": 100},
                  {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                  {"Name": "TransactionDate", "Value": 20260125163045},
                  {"Name": "PhoneNumber", "Value": 254712345678}
                ]
              }
            }
          }
        }
    """
    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        logger.exception("Invalid M-Pesa callback body")
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    logger.info(f"M-Pesa callback: {data}")

    try:
        stk = data['Body']['stkCallback']
        checkout_id = stk.get('CheckoutRequestID')
        result_code = stk.get('ResultCode')
        result_desc = stk.get('ResultDesc', '')

        txn = MpesaTransaction.objects.filter(
            checkout_request_id=checkout_id
        ).first()

        if not txn:
            logger.warning(f"Callback for unknown checkout_id: {checkout_id}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        txn.raw_callback = data
        txn.result_code = result_code
        txn.result_description = result_desc
        txn.completed_at = timezone.now()

        if result_code == 0:
            # Success — extract metadata
            meta = {item['Name']: item.get('Value')
                    for item in stk['CallbackMetadata']['Item']}

            receipt = meta.get('MpesaReceiptNumber', '')
            amount = meta.get('Amount', 0)

            # Guard against duplicates
            if MpesaTransaction.objects.filter(
                mpesa_receipt_number=receipt
            ).exclude(id=txn.id).exists():
                logger.warning(f"Duplicate receipt: {receipt}")
                txn.status = MpesaTransaction.Status.SUCCESS
                txn.mpesa_receipt_number = receipt
                txn.save()
                return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

            txn.mpesa_receipt_number = receipt
            txn.status = MpesaTransaction.Status.SUCCESS

            # Create Payment record (this triggers invoice update)
            if txn.invoice:
                payment = Payment.objects.create(
                    invoice=txn.invoice,
                    amount_kes=Decimal(str(amount)),
                    method=Payment.Method.MPESA,
                    external_reference=receipt,
                    notes=f"M-Pesa STK Push. Receipt: {receipt}",
                )
                txn.payment = payment

        elif result_code in (1032,):
            txn.status = MpesaTransaction.Status.CANCELLED
        elif result_code in (1037,):
            txn.status = MpesaTransaction.Status.TIMEOUT
        else:
            txn.status = MpesaTransaction.Status.FAILED

        txn.save()

    except Exception as e:
        logger.exception(f"Error processing M-Pesa callback: {e}")

    # Always respond 200 to Safaricom
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ==========================================================
# C2B — Validation + Confirmation (public)
# ==========================================================

@csrf_exempt
@require_POST
def mpesa_c2b_validation(request):
    """
    Safaricom calls this to validate a C2B payment BEFORE processing.
    Return "Accepted" to proceed, "Rejected" to stop.
    """
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@csrf_exempt
@require_POST
def mpesa_c2b_confirmation(request):
    """
    Safaricom calls this AFTER a successful C2B payment.
    We record the payment automatically.

    Payload:
        {
          "TransactionType": "Pay Bill",
          "TransID": "RKTQDM7W6S",
          "TransTime": "20260125163045",
          "TransAmount": "100.00",
          "BusinessShortCode": "174379",
          "BillRefNumber": "INV123",
          "MSISDN": "254712345678"
        }
    """
    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        logger.exception("Invalid C2B body")
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

    logger.info(f"C2B confirmation: {data}")

    try:
        receipt = data.get('TransID', '')
        amount = Decimal(str(data.get('TransAmount', 0)))
        bill_ref = data.get('BillRefNumber', '')
        phone = data.get('MSISDN', '')

        # Parse invoice_id from reference (format: "INV123")
        invoice_id = None
        if bill_ref.upper().startswith('INV'):
            try:
                invoice_id = int(bill_ref[3:])
            except (ValueError, TypeError):
                pass

        # Guard against duplicates
        if receipt and MpesaTransaction.objects.filter(
            mpesa_receipt_number=receipt
        ).exists():
            logger.info(f"Duplicate C2B receipt: {receipt}")
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        invoice = None
        school = None
        if invoice_id:
            invoice = Invoice.objects.filter(id=invoice_id).first()
            if invoice:
                school = invoice.student.school

        txn = MpesaTransaction.objects.create(
            school=school,
            invoice=invoice,
            transaction_type=MpesaTransaction.Type.C2B,
            phone=mpesa_service.normalize_phone(phone),
            amount=amount,
            mpesa_receipt_number=receipt,
            result_code=0,
            result_description='C2B Payment',
            status=MpesaTransaction.Status.SUCCESS,
            raw_callback=data,
            completed_at=timezone.now(),
        )

        # Auto-create payment if invoice matched
        if invoice:
            payment = Payment.objects.create(
                invoice=invoice,
                amount_kes=amount,
                method=Payment.Method.MPESA,
                external_reference=receipt,
                notes=f"M-Pesa C2B. Receipt: {receipt}",
            )
            txn.payment = payment
            txn.save(update_fields=['payment'])

    except Exception as e:
        logger.exception(f"C2B processing error: {e}")

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ==========================================================
# STATUS — Parent polls for result (private)
# ==========================================================

@login_required
def mpesa_status(request, checkout_request_id):
    """
    Return current status of an STK Push transaction.
    Parent portal polls this every 3 seconds.
    """
    txn = MpesaTransaction.objects.filter(
        checkout_request_id=checkout_request_id,
    ).first()

    if not txn:
        return JsonResponse({'success': False, 'error': 'Unknown transaction'}, status=404)

    # Authorization: parent can only see own
    if request.user.role == 'parent' and txn.invoice:
        try:
            request.user.parent_profile.students.get(id=txn.invoice.student_id)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    return JsonResponse({
        'success': True,
        'status': txn.status,
        'status_label': txn.get_status_display(),
        'is_successful': txn.is_successful,
        'is_pending': txn.is_pending,
        'receipt': txn.mpesa_receipt_number,
        'result_description': txn.result_description,
    })