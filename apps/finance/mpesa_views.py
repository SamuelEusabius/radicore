import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.finance.decorators import verify_mpesa_ip

from apps.students.models import Student
from apps.finance.models import (
    Invoice, Payment, StudentWallet, WalletTransaction
)
from apps.finance.mpesa_models import (
    MpesaTransaction, SchoolMpesaConfig, PlatformMpesaConfig
)
from apps.schools.models import School, SchoolSubscription

logger = logging.getLogger(__name__)


# ==========================================================
# ACCOUNTANT VIEWS
# ==========================================================

@login_required
def accountant_mpesa_settings(request):
    """Accountant configures school M-Pesa credentials."""
    if request.user.role not in ('accountant', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    config, _ = SchoolMpesaConfig.objects.get_or_create(school=school)

    if request.method == 'POST':
        config.paybill_number = request.POST.get('paybill_number', '').strip()
        config.consumer_key = request.POST.get('consumer_key', '').strip()
        config.consumer_secret = request.POST.get('consumer_secret', '').strip()
        config.passkey = request.POST.get('passkey', '').strip()
        config.callback_url = request.build_absolute_uri('/api/finance/mpesa/c2b/confirmation/')
        config.save()
        messages.success(request, 'M-Pesa settings saved successfully!')
        return redirect('accountant_mpesa_settings')

    return render(request, 'dashboard/finance/mpesa_settings.html', {'config': config})


@login_required
def accountant_mpesa_ledger(request):
    """View all M-Pesa transactions for the school."""
    if request.user.role not in ('accountant', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    transactions = MpesaTransaction.objects.filter(school=school).order_by('-created_at')[:100]

    return render(request, 'dashboard/finance/mpesa_ledger.html', {
        'transactions': transactions,
    })


@login_required
def accountant_manual_mpesa(request):
    """Manually record an M-Pesa payment (for offline payments)."""
    if request.user.role not in ('accountant', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    if request.method == 'POST':
        admission_number = request.POST.get('admission_number', '').strip().upper()
        amount = Decimal(request.POST.get('amount', '0'))
        receipt = request.POST.get('receipt', '').strip()
        phone = request.POST.get('phone', '').strip()

        student = Student.objects.filter(
            school=request.user.school, admission_number=admission_number
        ).first()

        if not student:
            messages.error(request, f"Student {admission_number} not found.")
            return redirect('accountant_manual_mpesa')

        if MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
            messages.error(request, f"Receipt {receipt} already exists.")
            return redirect('accountant_manual_mpesa')

        with transaction.atomic():
            MpesaTransaction.objects.create(
                school=request.user.school, student=student, phone=phone, amount=amount,
                mpesa_receipt_number=receipt, status='success', purpose='fees',
                bill_ref_number=admission_number, transaction_type='manual',
                result_description="Manually recorded by accountant"
            )

            invoice = Invoice.objects.filter(student=student).exclude(status='paid').order_by('due_date').first()
            if invoice:
                invoice.amount_paid += amount
                if invoice.amount_paid >= invoice.amount_due:
                    invoice.status = 'paid'
                invoice.save()

                Payment.objects.create(
                    invoice=invoice, amount_kes=amount, method='mpesa',
                    reference=receipt, paid_at=timezone.now()
                )

        messages.success(request, f"Payment of KES {amount} recorded for {student.full_name}.")
        return redirect('accountant_mpesa_ledger')

    return render(request, 'dashboard/finance/mpesa_manual.html')


# ==========================================================
# SAFARICOM CALLBACKS (SECURED)
# ==========================================================

@csrf_exempt
@verify_mpesa_ip
def mpesa_c2b_confirmation(request):
    """Safaricom hits this when a parent pays via Paybill."""
    if request.method != 'POST':
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid Method"})

    try:
        data = json.loads(request.body)
        paybill = data.get('BusinessShortCode')
        account_ref = data.get('BillRefNumber', '').strip().upper()
        amount = Decimal(str(data.get('TransAmount', 0)))
        receipt = data.get('TransID')
        phone = data.get('MSISDN')

        # IDEMPOTENCY CHECK
        if MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

        config = SchoolMpesaConfig.objects.filter(paybill_number=paybill, is_active=True).first()
        if not config:
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Paybill not recognized"})

        school = config.school

        purpose = 'fees'
        if account_ref.endswith('-WAL'):
            purpose = 'wallet'
            admission_number = account_ref.replace('-WAL', '')
        else:
            admission_number = account_ref

        student = Student.objects.filter(school=school, admission_number=admission_number).first()
        if not student:
            MpesaTransaction.objects.create(
                school=school, phone=phone, amount=amount, mpesa_receipt_number=receipt,
                status='success', purpose='other', bill_ref_number=account_ref,
                transaction_type='c2b', result_description="Student admission number not found"
            )
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted but student not found"})

        with transaction.atomic():
            if MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed (race)"})

            MpesaTransaction.objects.create(
                school=school, student=student, phone=phone, amount=amount,
                mpesa_receipt_number=receipt, status='success', purpose=purpose,
                bill_ref_number=account_ref, transaction_type='c2b',
                result_description="Auto-processed via Paybill"
            )

            if purpose == 'fees':
                invoice = Invoice.objects.filter(student=student).exclude(status='paid').order_by('due_date').first()
                if invoice:
                    remaining_due = invoice.amount_due - invoice.amount_paid
                    if amount > remaining_due:
                        invoice.amount_paid = invoice.amount_due
                        invoice.status = 'paid'
                        invoice.save()

                        excess = amount - remaining_due
                        student.credit_balance += excess
                        student.save()

                        Payment.objects.create(
                            invoice=invoice, amount_kes=amount, method='mpesa',
                            reference=receipt, paid_at=timezone.now(),
                            notes=f"Includes KES {excess} overpayment (saved as credit)"
                        )
                    else:
                        invoice.amount_paid += amount
                        if invoice.amount_paid >= invoice.amount_due:
                            invoice.status = 'paid'
                        invoice.save()

                        Payment.objects.create(
                            invoice=invoice, amount_kes=amount, method='mpesa',
                            reference=receipt, paid_at=timezone.now()
                        )

            elif purpose == 'wallet':
                wallet, _ = StudentWallet.objects.get_or_create(student=student, school=school)
                wallet.balance += amount
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet, tx_type='topup', source='mpesa', status='success',
                    amount=amount, balance_after=wallet.balance, reference=receipt,
                    notes='Auto top-up via Paybill'
                )

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.error(f"M-Pesa Callback Error: {str(e)}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)})


@csrf_exempt
@verify_mpesa_ip
def platform_c2b_confirmation(request):
    """Safaricom hits this when a SCHOOL pays for their SaaS subscription."""
    if request.method != 'POST':
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid Method"})

    try:
        data = json.loads(request.body)
        account_ref = data.get('BillRefNumber', '').strip().upper()
        amount = Decimal(str(data.get('TransAmount', 0)))
        receipt = data.get('TransID')
        phone = data.get('MSISDN')

        if MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Already processed"})

        school = School.objects.filter(code=account_ref).first()
        if not school:
            logger.error(f"SaaS Payment received but School Code '{account_ref}' not found.")
            return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted but School not found"})

        with transaction.atomic():
            sub, _ = SchoolSubscription.objects.get_or_create(school=school)
            sub.status = 'active'
            sub.save()

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
    except Exception as e:
        return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)})