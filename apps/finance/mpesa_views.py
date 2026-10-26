import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from .mpesa_models import MpesaTransaction, SchoolMpesaConfig
from .models import Payment, Invoice
from .wallet_models import StudentWallet, WalletTransaction
from apps.students.models import Student

logger = logging.getLogger(__name__)


# ==========================================================
# ACCOUNTANT VIEWS (Ledger & Settings)
# ==========================================================

@login_required
def accountant_mpesa_ledger(request):
    """Accountant view to see ALL M-Pesa transactions."""
    if request.user.role not in ('accountant', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    transactions = MpesaTransaction.objects.filter(school=school).order_by('-created_at')
    
    if query:
        transactions = transactions.filter(
            Q(phone__icontains=query) | 
            Q(mpesa_receipt_number__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query)
        )
    if status_filter:
        transactions = transactions.filter(status=status_filter)

    paginator = Paginator(transactions, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    success_txns = transactions.filter(status='success')
    total_fees = sum(t.amount for t in success_txns if t.purpose == 'fees')
    total_wallet = sum(t.amount for t in success_txns if t.purpose == 'wallet')

    return render(request, 'dashboard/finance/mpesa_ledger.html', {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'total_fees': total_fees,
        'total_wallet': total_wallet,
    })


@login_required
def accountant_manual_mpesa(request):
    """Manual entry for when Safaricom sends money but callback fails."""
    if request.user.role not in ('accountant', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    
    if request.method == 'POST':
        student_id = request.POST.get('student')
        phone = request.POST.get('phone')
        amount = request.POST.get('amount')
        receipt = request.POST.get('receipt')
        purpose = request.POST.get('purpose')
        
        student = get_object_or_404(Student, id=student_id, school=school)
        
        txn = MpesaTransaction.objects.create(
            school=school,
            student=student,
            phone=phone,
            amount=amount,
            mpesa_receipt_number=receipt,
            status='success',
            purpose=purpose,
            transaction_type='manual',
            result_description='Manually logged by accountant',
            initiated_by=request.user
        )
        
        if purpose == 'fees':
            invoice = Invoice.objects.filter(student=student).exclude(status='paid').order_by('due_date').first()
            if invoice:
                invoice.amount_paid += Decimal(amount)
                if invoice.amount_paid >= invoice.amount_due:
                    invoice.status = 'paid'
                invoice.save()
                
                Payment.objects.create(
                    invoice=invoice,
                    amount_kes=amount,
                    method='mpesa',
                    reference=receipt,
                    paid_at=timezone.now(),
                    recorded_by=request.user,
                    mpesa_transaction=txn
                )
        elif purpose == 'wallet':
            wallet, _ = StudentWallet.objects.get_or_create(student=student, school=school)
            wallet.balance += Decimal(amount)
            wallet.save()
            
            WalletTransaction.objects.create(
                wallet=wallet,
                tx_type='topup',
                source='mpesa',
                status='success',
                amount=amount,
                balance_after=wallet.balance,
                reference=receipt,
                notes='Manual M-Pesa top-up by accountant'
            )

        messages.success(request, f'Transaction {receipt} logged successfully and student account updated.')
        return redirect('accountant_mpesa_ledger')

    students = Student.objects.filter(school=school, is_active=True).only(
    'id', 'first_name', 'last_name', 'admission_number', 'class_level'
).order_by('first_name')
    return render(request, 'dashboard/finance/manual_mpesa.html', {'students': students})


@login_required
def accountant_mpesa_settings(request):
    """Accountant enters their school's Paybill details."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')
        
    config, created = SchoolMpesaConfig.objects.get_or_create(school=request.user.school)
    
    if request.method == 'POST':
        config.paybill_number = request.POST.get('paybill_number')
        config.consumer_key = request.POST.get('consumer_key')
        config.consumer_secret = request.POST.get('consumer_secret')
        config.passkey = request.POST.get('passkey')
        
        config.callback_url = request.build_absolute_uri(reverse('mpesa_c2b_confirmation'))
        config.save()
        messages.success(request, 'M-Pesa Settings saved successfully!')
        return redirect('accountant_mpesa_settings')
        
    return render(request, 'dashboard/finance/mpesa_settings.html', {'config': config})


# ==========================================================
# SAFARICOM CALLBACKS (The "Brain")
# ==========================================================

@csrf_exempt
def mpesa_c2b_confirmation(request):
    """Safaricom hits this when a parent pays via Paybill."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            paybill = data.get('BusinessShortCode')
            account_ref = data.get('BillRefNumber', '').strip().upper()
            amount = Decimal(str(data.get('TransAmount', 0)))
            receipt = data.get('TransID')
            phone = data.get('MSISDN')
            
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
                txn = MpesaTransaction.objects.create(
                    school=school, student=student, phone=phone, amount=amount,
                    mpesa_receipt_number=receipt, status='success', purpose=purpose,
                    bill_ref_number=account_ref, transaction_type='c2b',
                    result_description="Auto-processed via Paybill"
                )
                
                if purpose == 'fees':
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
            
    return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid Method"})

from apps.schools.models import School, SchoolSubscription
from django.utils import timezone
from datetime import timedelta

@csrf_exempt
def platform_c2b_confirmation(request):
    """Safaricom hits this when a SCHOOL pays for their SaaS subscription."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            paybill = data.get('BusinessShortCode')
            account_ref = data.get('BillRefNumber', '').strip().upper() # e.g., NAIROBI01
            amount = Decimal(str(data.get('TransAmount', 0)))
            receipt = data.get('TransID')
            phone = data.get('MSISDN')
            
            # 1. Find the School via the Account Reference (School Code)
            school = School.objects.filter(code=account_ref).first()
            
            if not school:
                # Money received, but school code is invalid
                logger.error(f"SaaS Payment received but School Code '{account_ref}' not found.")
                return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted but School not found"})

            # 2. Process the Subscription
            with transaction.atomic():
                sub, created = SchoolSubscription.objects.get_or_create(school=school)
                
                # Log the payment
                sub.status = 'active'
                sub.total_paid_kes += amount
                sub.last_payment_date = timezone.now()
                sub.last_payment_method = 'M-Pesa'
                sub.last_payment_reference = receipt
                sub.payment_notes = f"Platform Paybill Payment via {phone}"
                
                # 3. Extend their subscription (Default: add 30 days for now. 
                # You can make this dynamic based on the plan later)
                if not sub.paid_until or sub.paid_until < timezone.now().date():
                    sub.paid_until = timezone.now().date() + timedelta(days=30)
                else:
                    sub.paid_until += timedelta(days=30)
                
                sub.save()
                
                # 4. Unblock the School if it was blocked
                if not school.is_active:
                    school.is_active = True
                    school.blocked_message = None
                    school.save()

            return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})
            
        except Exception as e:
            logger.error(f"Platform Callback Error: {str(e)}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)})
            
    return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid Method"})