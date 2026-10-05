"""
Auto-match or queue M-Pesa payments.

Tries multiple strategies to match a payment to a student + invoice.
If all fail, saves to UnallocatedPayment for manual reconciliation.
"""
from decimal import Decimal
from django.utils import timezone
from .unallocated_notifications import notify_accountant_of_unallocated


def try_auto_match(mpesa_txn, school):
    """
    Attempt to match an M-Pesa payment to a student + invoice.

    Returns:
        (payment, unallocated) — payment if matched, unallocated always set
    """
    from apps.finance.models import Invoice, Payment
    from apps.students.models import Student
    from .unallocated_models import UnallocatedPayment, UnallocatedAllocation

    # Extract what we know
    account_ref = ''
    if mpesa_txn.raw_callback:
        account_ref = (
            mpesa_txn.raw_callback.get('BillRefNumber')
            or mpesa_txn.raw_callback.get('account_reference', '')
        )
    account_ref = (account_ref or '').strip()

    phone = mpesa_txn.phone
    amount = Decimal(str(mpesa_txn.amount))
    receipt = mpesa_txn.mpesa_receipt_number

    student = None
    strategy = 'unmatched'

    # --- Strategy 1: Exact admission number match ---
    if account_ref:
        student = Student.objects.filter(
            school=school, admission_number__iexact=account_ref
        ).first()
        if student:
            strategy = 'admission_number'

    # --- Strategy 2: Extract admission number from reference ---
    if not student and account_ref:
        import re
        for token in re.findall(r'[A-Za-z]*\d+[A-Za-z]*', account_ref):
            student = Student.objects.filter(
                school=school, admission_number__iexact=token
            ).first()
            if student:
                strategy = 'admission_number_partial'
                break

    # --- Strategy 3: Match by parent phone ---
    if not student and phone:
        from apps.parents.models import Parent
        try:
            phone_tail = phone[-9:]
            parent = Parent.objects.filter(
                user__school=school,
                user__phone__endswith=phone_tail,
            ).first()
            if not parent:
                # Try without the +254 country code
                parent = Parent.objects.filter(
                    user__school=school,
                    user__phone__contains=phone_tail,
                ).first()

            if parent:
                children = parent.students.filter(is_active=True)
                if children.count() == 1:
                    student = children.first()
                    strategy = 'parent_phone'
                elif children.count() > 1:
                    for child in children:
                        if _has_outstanding(child):
                            student = child
                            strategy = 'parent_phone_outstanding'
                            break
        except Exception:
            pass

    # --- No student matched → queue as unallocated ---
        # --- No student matched → queue as unallocated ---
    if not student:
        unallocated, _ = UnallocatedPayment.objects.get_or_create(
            mpesa_receipt=receipt,
            defaults={
                'school': school,
                'amount': amount,
                'phone': phone,
                'account_reference': account_ref,
                'transaction_date': mpesa_txn.completed_at or timezone.now(),
                'mpesa_transaction': mpesa_txn,
                'raw_callback': mpesa_txn.raw_callback or {},
                'status': 'unallocated',
                'notes': f'Auto-queued: could not match reference "{account_ref}" or phone {phone}.',
            }
        )
        # Notify accountants
        try:
            notify_accountant_of_unallocated(unallocated)
        except Exception:
            pass
        return None, unallocated

    # --- Student matched → find outstanding invoice ---
    invoice = _find_outstanding_invoice(student, amount)

    if invoice:
        payment = Payment.objects.create(
            invoice=invoice,
            amount_kes=amount,
            method='mpesa',
            external_reference=receipt,
            notes=f'C2B M-Pesa. Strategy: {strategy}',
        )
        # Update invoice status
        invoice.amount_paid += amount
        invoice.save()
        invoice.update_status()

            # --- Student matched but no invoice to apply → queue for bursar ---
    unallocated, _ = UnallocatedPayment.objects.get_or_create(
        mpesa_receipt=receipt,
        defaults={
            'school': school,
            'amount': amount,
            'phone': phone,
            'account_reference': account_ref,
            'transaction_date': mpesa_txn.completed_at or timezone.now(),
            'mpesa_transaction': mpesa_txn,
            'raw_callback': mpesa_txn.raw_callback or {},
            'status': 'unallocated',
            'notes': (
                f'Student matched ({student.full_name}, {student.admission_number}) '
                f'via {strategy}, but no outstanding invoice found.'
            ),
        }
    )
    # Notify accountants
    try:
        notify_accountant_of_unallocated(unallocated)
    except Exception:
        pass
    return None, unallocated

    # --- Student matched but no invoice to apply → queue for bursar ---
    unallocated, _ = UnallocatedPayment.objects.get_or_create(
        mpesa_receipt=receipt,
        defaults={
            'school': school,
            'amount': amount,
            'phone': phone,
            'account_reference': account_ref,
            'transaction_date': mpesa_txn.completed_at or timezone.now(),
            'mpesa_transaction': mpesa_txn,
            'raw_callback': mpesa_txn.raw_callback or {},
            'status': 'unallocated',
            'notes': (
                f'Student matched ({student.full_name}, {student.admission_number}) '
                f'via {strategy}, but no outstanding invoice found.'
            ),
        }
    )
    return None, unallocated


def _has_outstanding(student):
    """Check if a student has any outstanding invoice."""
    from apps.finance.models import Invoice
    return Invoice.objects.filter(
        student=student, status__in=['unpaid', 'partial', 'overdue']
    ).exists()


def _find_outstanding_invoice(student, amount):
    """Find the best invoice to apply the payment to."""
    from apps.finance.models import Invoice
    invoices = Invoice.objects.filter(
        student=student, status__in=['unpaid', 'partial', 'overdue']
    ).order_by('due_date')

    # Prefer invoice matching the amount exactly
    for inv in invoices:
        if inv.balance == amount:
            return inv

    # Otherwise first with balance > 0
    for inv in invoices:
        if inv.balance > 0:
            return inv

    return None