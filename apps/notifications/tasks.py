"""
Notification tasks — sent via Celery.
Includes SMS, email, and in-app notifications.
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Notification
from .services.sms import send_sms, send_bulk_sms, normalize_phone


# ==========================================================
# FEE REMINDER (single invoice)
# ==========================================================

@shared_task
def send_fee_reminder(invoice_id):
    """
    Send SMS + email + in-app notification to parents
    for a single unpaid/overdue invoice.
    """
    from apps.finance.models import Invoice

    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return f'Invoice {invoice_id} not found'

    student = invoice.student
    parents = student.parents.all()
    if not parents:
        return f'No parents linked to {student}'

    sms_text = (
        f"Hello, school fees for {student.first_name} {student.last_name} "
        f"({student.admission_number}) balance is KES {invoice.balance:.0f}. "
        f"Due {invoice.due_date.strftime('%d/%m/%Y')}. Thank you."
    )
    email_text = (
        f"Fee Reminder\n\n"
        f"Student: {student.full_name}\n"
        f"Balance: KES {invoice.balance:.2f}\n"
        f"Due Date: {invoice.due_date}\n"
        f"Please settle the balance at your earliest convenience."
    )

    count = 0
    for parent in parents:
        user = parent.user

        # In-app notification
        Notification.objects.create(
            recipient=user,
            channel='in_app',
            title='Fee Payment Due',
            message=f'KES {invoice.balance:.0f} due for {student.full_name} on {invoice.due_date}.',
        )

        # Email
        if user.email:
            try:
                send_mail(
                    subject=f'Fee Reminder — {student.full_name}',
                    message=email_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        # SMS
        phone = user.phone or parent.phone
        if phone:
            send_sms(phone, sms_text)

        count += 1

    return f'Queued reminders for {count} parents of {student.full_name}'


# ==========================================================
# DAILY FEE REMINDERS (bulk)
# ==========================================================

@shared_task
def send_daily_fee_reminders():
    """
    Find all invoices due within 7 days (or overdue) and queue reminders.
    """
    from apps.finance.models import Invoice
    from datetime import date, timedelta

    today = date.today()
    threshold = today + timedelta(days=7)

    invoices = Invoice.objects.filter(
        status__in=['unpaid', 'partial', 'overdue'],
        due_date__lte=threshold,
    ).select_related('student')

    count = 0
    for inv in invoices:
        send_fee_reminder.delay(inv.id)
        count += 1

    return f'Queued {count} fee reminders.'


# ==========================================================
# PAYMENT CONFIRMATION
# ==========================================================

@shared_task
def send_payment_confirmation(payment_id):
    """
    Send SMS + in-app notification to parents confirming a payment.
    """
    from apps.finance.models import Payment

    try:
        payment = Payment.objects.select_related('invoice__student').get(id=payment_id)
    except Payment.DoesNotExist:
        return f'Payment {payment_id} not found'

    student = payment.invoice.student
    invoice = payment.invoice
    parents = student.parents.all()

    sms_text = (
        f"Payment received: KES {payment.amount_kes:.0f} for {student.first_name} "
        f"({student.admission_number}). Ref: {payment.reference}. "
        f"Balance: KES {invoice.balance:.0f}. Thank you."
    )

    for parent in parents:
        user = parent.user

        Notification.objects.create(
            recipient=user,
            channel='in_app',
            title='Payment Received',
            message=f'KES {payment.amount_kes:.0f} received for {student.full_name}. Balance: KES {invoice.balance:.0f}.',
        )

        phone = user.phone or parent.phone
        if phone:
            send_sms(phone, sms_text)

    return f'Payment confirmation sent for {student.full_name}'


# ==========================================================
# ATTENDANCE ALERT
# ==========================================================

@shared_task
def send_absence_alert(attendance_id):
    """
    Send SMS to parents when a student is marked absent.
    """
    from apps.attendance.models import Attendance

    try:
        att = Attendance.objects.select_related('student').get(id=attendance_id)
    except Attendance.DoesNotExist:
        return f'Attendance {attendance_id} not found'

    if att.status not in ('A', 'L'):
        return 'Not an absence/late — skipping'

    student = att.student
    parents = student.parents.all()

    status_text = 'absent' if att.status == 'A' else 'late'
    sms_text = (
        f"{student.first_name} {student.last_name} ({student.admission_number}) "
        f"was marked {status_text} today, {att.date.strftime('%d/%m/%Y')}."
    )

    for parent in parents:
        phone = parent.user.phone or parent.phone
        if phone:
            send_sms(phone, sms_text)

        Notification.objects.create(
            recipient=parent.user,
            channel='in_app',
            title=f'Attendance Alert — {student.first_name}',
            message=sms_text,
        )

    return f'Absence alert sent for {student.full_name}'


# ==========================================================
# BULK SMS (custom)
# ==========================================================

@shared_task
def send_custom_bulk_sms(school_id, message, recipient_filter='all', phones=None):
    """
    Send a bulk SMS to a group of parents.
    
    recipient_filter options:
        'all'          — all parents with phones
        'unpaid'       — parents with unpaid invoices
        'class:<id>'   — parents of students in a class
        'custom'       — use the phones list
    """
    from apps.parents.models import Parent
    from apps.students.models import Student

    if recipient_filter == 'custom' and phones:
        result = send_bulk_sms(phones, message)
        return f"Custom SMS: {result['message']}"

    # Build phone list
    qs = Parent.objects.filter(user__school_id=school_id)

    if recipient_filter == 'unpaid':
        from apps.finance.models import Invoice
        student_ids = Invoice.objects.filter(
            student__school_id=school_id,
            status__in=['unpaid', 'partial', 'overdue']
        ).values_list('student_id', flat=True).distinct()
        qs = qs.filter(students__id__in=student_ids)

    elif recipient_filter.startswith('class:'):
        class_id = recipient_filter.split(':', 1)[1]
        student_ids = Student.objects.filter(
            school_id=school_id, class_level_id=class_id
        ).values_list('id', flat=True)
        qs = qs.filter(students__id__in=student_ids)

    qs = qs.distinct()

    phones_list = []
    for p in qs:
        phone = p.user.phone or p.phone
        if phone:
            phones_list.append(phone)

    if not phones_list:
        return 'No recipients with phone numbers'

    result = send_bulk_sms(phones_list, message)
    return f"Bulk SMS: {result['message']}"


# ==========================================================
# TEST
# ==========================================================

@shared_task
def send_test_sms(phone, message='Test SMS from School MS'):
    """Quick test task — used from the dashboard."""
    result = send_sms(phone, message)
    return results
@shared_task
def run_smart_scan():
    """Automatically run all smart alert detection rules."""
    from .services.smart_alerts import run_all_detections
    count = run_all_detections()
    return f'Smart scan complete: {count} new alerts'