"""
Unallocated Payments — Bursar's reconciliation views.

Handles:
  - Queue listing
  - Payment detail
  - Reassign to student
  - Split across siblings
  - Create invoice for amount
  - Reject payment
  - Reports
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .unallocated_models import UnallocatedPayment, UnallocatedAllocation


def _bursar_required(request):
    return request.user.role in ('accountant', 'principal')


# ============================================================
# QUEUE
# ============================================================

@login_required
def unallocated_queue(request):
    """Bursar's main queue of unallocated payments."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = UnallocatedPayment.objects.filter(school=school).select_related(
        'mpesa_transaction', 'resolved_by'
    )

    # Default filter: only unallocated
    status = request.GET.get('status', 'unallocated')
    if status:
        qs = qs.filter(status=status)

    # Search
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(mpesa_receipt__icontains=search) |
            Q(phone__icontains=search) |
            Q(account_reference__icontains=search) |
            Q(payer_name__icontains=search)
        )

    # Date filter
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')
    if date_from:
        qs = qs.filter(transaction_date__date__gte=date_from)
    if date_to:
        qs = qs.filter(transaction_date__date__lte=date_to)

    qs = qs.order_by('-transaction_date')

    # Stats
    all_qs = UnallocatedPayment.objects.filter(school=school)
    stats = {
        'unallocated': all_qs.filter(status='unallocated').count(),
        'allocated': all_qs.filter(status='allocated').count(),
        'total_unallocated': all_qs.filter(
            status='unallocated'
        ).aggregate(t=Sum('amount'))['t'] or 0,
        'total_all': all_qs.count(),
        'resolved_this_week': all_qs.filter(
            resolved_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count(),
    }

    return render(request, 'dashboard/finance/unallocated/queue.html', {
        'payments': qs[:200],
        'stats': stats,
        'status_filter': status,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
    })


# ============================================================
# DETAIL
# ============================================================

@login_required
def unallocated_detail(request, payment_id):
    """View a single unallocated payment."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    payment = get_object_or_404(
        UnallocatedPayment, id=payment_id, school=request.user.school
    )
    allocations = payment.allocations.select_related(
        'student', 'invoice', 'payment'
    ).order_by('-created_at')

    return render(request, 'dashboard/finance/unallocated/detail.html', {
        'payment': payment,
        'allocations': allocations,
    })


# ============================================================
# REASSIGN — Assign to a single student
# ============================================================

@login_required
def unallocated_reassign(request, payment_id):
    """Reassign an unallocated payment to a specific student's invoice."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.finance.models import Invoice, Payment

    payment = get_object_or_404(
        UnallocatedPayment, id=payment_id, school=request.user.school
    )

    if payment.is_resolved:
        messages.warning(request, 'This payment has already been resolved.')
        return redirect('unallocated_detail', payment_id=payment.id)

    # Search students
    search = request.GET.get('q', '').strip()
    students = Student.objects.filter(
        school=request.user.school, is_active=True
    )
    if search:
        students = students.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search)
        )
    students = students.order_by('first_name', 'last_name')[:30]

    if request.method == 'POST':
        student_id = request.POST.get('student', '').strip()
        invoice_id = request.POST.get('invoice', '').strip()
        amount = request.POST.get('amount', '').strip()
        notes = request.POST.get('notes', '').strip()

        student = get_object_or_404(
            Student, id=student_id, school=request.user.school
        )

        try:
            amount = Decimal(amount)
            if amount <= 0 or amount > payment.amount:
                raise ValueError()
        except Exception:
            messages.error(request, f'Invalid amount (must be ≤ {payment.amount}).')
            return redirect('unallocated_reassign', payment_id=payment.id)

        # Get or auto-pick invoice
        invoice = None
        if invoice_id:
            invoice = Invoice.objects.filter(id=invoice_id, student=student).first()

        if not invoice:
            invoice = Invoice.objects.filter(
                student=student,
                status__in=['unpaid', 'partial', 'overdue']
            ).order_by('due_date').first()

        # Create payment
        if invoice:
            payment_obj = Payment.objects.create(
                invoice=invoice,
                amount_kes=amount,
                method=Payment.Method.MPESA,
                external_reference=payment.mpesa_receipt,
                notes=f'Reassigned from unallocated. {notes}'.strip(),
            )
            invoice.amount_paid += amount
            invoice.save()
            invoice.update_status()
        else:
            messages.warning(
                request,
                f'{student.full_name} has no outstanding invoice. Creating new...'
            )
            return redirect('unallocated_detail', payment_id=payment.id)

        # Allocate
        UnallocatedAllocation.objects.create(
            unallocated_payment=payment,
            student=student,
            invoice=invoice,
            payment=payment_obj,
            amount=amount,
            notes=notes or f'Reassigned by {request.user.get_full_name()}',
        )

        # Update status
        total_allocated = sum(a.amount for a in payment.allocations.all())
        if total_allocated >= payment.amount:
            payment.status = UnallocatedPayment.Status.ALLOCATED
            payment.resolved_at = timezone.now()
            payment.resolved_by = request.user
        else:
            payment.status = UnallocatedPayment.Status.ALLOCATED  # partial allocation
            # We could add a 'partial' status if needed

        if notes:
            payment.notes = (payment.notes + '\n' + notes).strip()
        payment.save()

        messages.success(
            request,
            f'KES {amount:,.0f} assigned to {student.full_name} — invoice #{invoice.id}'
        )
        return redirect('unallocated_queue')

    return render(request, 'dashboard/finance/unallocated/reassign.html', {
        'payment': payment,
        'students': students,
        'search': search,
    })


# ============================================================
# SPLIT — Across multiple students (siblings)
# ============================================================

@login_required
def unallocated_split(request, payment_id):
    """Split an unallocated payment across multiple students."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.finance.models import Invoice, Payment

    payment = get_object_or_404(
        UnallocatedPayment, id=payment_id, school=request.user.school
    )

    if payment.is_resolved:
        messages.warning(request, 'This payment has already been resolved.')
        return redirect('unallocated_detail', payment_id=payment.id)

    if request.method == 'POST':
        # Expect POST with student_<id>, amount_<id>, invoice_<id>
        splits = []
        for key in request.POST:
            if key.startswith('student_') and request.POST.get(f'amount_{key[8:]}'):
                sid = key[8:]
                amt_str = request.POST.get(f'amount_{sid}', '').strip()
                inv_str = request.POST.get(f'invoice_{sid}', '').strip()
                if not amt_str:
                    continue
                try:
                    amt = Decimal(amt_str)
                    if amt <= 0:
                        continue
                    splits.append((int(sid), amt, int(inv_str) if inv_str else None))
                except Exception:
                    continue

        if not splits:
            messages.error(request, 'No valid splits provided.')
            return redirect('unallocated_split', payment_id=payment.id)

        total = sum(a for _, a, _ in splits)
        if total > payment.amount:
            messages.error(
                request,
                f'Total split (KES {total:,.0f}) exceeds payment ({payment.amount:,.0f}).'
            )
            return redirect('unallocated_split', payment_id=payment.id)

        # Apply each split
        for sid, amt, inv_id in splits:
            student = Student.objects.filter(id=sid, school=request.user.school).first()
            if not student:
                continue

            invoice = None
            if inv_id:
                invoice = Invoice.objects.filter(id=inv_id, student=student).first()
            if not invoice:
                invoice = Invoice.objects.filter(
                    student=student,
                    status__in=['unpaid', 'partial', 'overdue']
                ).order_by('due_date').first()

            if not invoice:
                messages.warning(request, f'No invoice for {student.full_name}')
                continue

            pay = Payment.objects.create(
                invoice=invoice,
                amount_kes=amt,
                method=Payment.Method.MPESA,
                external_reference=payment.mpesa_receipt,
                notes=f'Split from unallocated payment {payment.mpesa_receipt}',
            )
            invoice.amount_paid += amt
            invoice.save()
            invoice.update_status()

            UnallocatedAllocation.objects.create(
                unallocated_payment=payment,
                student=student,
                invoice=invoice,
                payment=pay,
                amount=amt,
                notes=f'Split by {request.user.get_full_name()}',
            )

        # Mark resolved
        payment.status = UnallocatedPayment.Status.ALLOCATED
        payment.resolved_at = timezone.now()
        payment.resolved_by = request.user
        payment.save()

        messages.success(request, f'Split applied: {len(splits)} allocation(s).')
        return redirect('unallocated_queue')

    return render(request, 'dashboard/finance/unallocated/split.html', {
        'payment': payment,
    })


# ============================================================
# REJECT — Not our payment
# ============================================================

@login_required
def unallocated_reject(request, payment_id):
    """Mark as rejected (not our payment)."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    payment = get_object_or_404(
        UnallocatedPayment, id=payment_id, school=request.user.school
    )

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        payment.status = UnallocatedPayment.Status.REJECTED
        payment.resolved_at = timezone.now()
        payment.resolved_by = request.user
        payment.notes = (payment.notes + f'\nRejected: {reason}').strip()
        payment.save()
        messages.success(request, 'Payment marked as rejected.')
        return redirect('unallocated_queue')

    return render(request, 'dashboard/finance/unallocated/reject.html', {
        'payment': payment,
    })


# ============================================================
# REPORTS
# ============================================================

@login_required
def unallocated_reports(request):
    """Aging + activity reports."""
    if not _bursar_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = UnallocatedPayment.objects.filter(school=school)

    # Aging buckets for unallocated
    unallocated = qs.filter(status='unallocated')
    now = timezone.now()
    aging = {
        'under_1h':  unallocated.filter(created_at__gte=now - timezone.timedelta(hours=1)).count(),
        'under_24h': unallocated.filter(
            created_at__gte=now - timezone.timedelta(days=1),
            created_at__lt=now - timezone.timedelta(hours=1)
        ).count(),
        'under_7d': unallocated.filter(
            created_at__gte=now - timezone.timedelta(days=7),
            created_at__lt=now - timezone.timedelta(days=1)
        ).count(),
        'over_7d': unallocated.filter(created_at__lt=now - timezone.timedelta(days=7)).count(),
    }

    # Recently resolved
    resolved = qs.exclude(status='unallocated').select_related(
        'resolved_by'
    ).order_by('-resolved_at')[:50]

    # Top resolvers
    resolvers = qs.exclude(resolved_by__isnull=True).values(
        'resolved_by__first_name', 'resolved_by__last_name', 'resolved_by__email'
    ).annotate(count=Count('id')).order_by('-count')[:10]

    return render(request, 'dashboard/finance/unallocated/reports.html', {
        'aging': aging,
        'resolved': resolved,
        'resolvers': resolvers,
        'total_unallocated': unallocated.aggregate(t=Sum('amount'))['t'] or 0,
    })