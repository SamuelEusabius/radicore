"""
Finance views:
- Accountant dashboard & invoices
- Fee structure management (list, add, edit, delete, bulk, matrix)
- Invoice generation & payment recording
- Expenditures (list, add, edit, delete, PDF)
- Fee statements (class-wide)
- Financial reports
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import date, datetime, timedelta

from apps.accounts.decorators import (
    role_required, school_staff_only, accountant_only,
)

from apps.core.pdf_utils import build_pdf_context



@login_required
@accountant_only
def accountant_dash(request):
    from django.db.models import Sum, Count, F
    from django.db.models.functions import TruncMonth
    from django.utils import timezone
    from datetime import timedelta
    from apps.finance.models import Invoice, Payment
    from apps.students.models import Student

    school = request.user.school

    # ---------- Invoices: aggregate in the DB ----------
    invoice_qs = Invoice.objects.filter(student__school=school)

    agg = invoice_qs.aggregate(
        total_invoiced=Sum('amount_due'),
        total_paid=Sum('amount_paid'),
        invoice_count=Count('id'),
    )

    total_invoiced = agg['total_invoiced'] or 0
    total_paid     = agg['total_paid'] or 0
    outstanding    = total_invoiced - total_paid
    invoice_count  = agg['invoice_count'] or 0

    collection_rate = round(
        (float(total_paid) / float(total_invoiced) * 100) if total_invoiced else 0,
        1
    )

    # ---------- Status counts (single grouped query) ----------
    status_counts = dict(
        invoice_qs.values_list('status').annotate(c=Count('id'))
    )
    overdue_count = status_counts.get('overdue', 0)
    unpaid_count  = status_counts.get('unpaid', 0)

    # ---------- Recent payments (5 latest) ----------
    recent_payments = (
        Payment.objects
        .filter(invoice__student__school=school)
        .select_related('invoice__student')
        .order_by('-paid_at')[:5]
    )

    # ---------- Collections trend: last 6 months ----------
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_rows = (
        Payment.objects
        .filter(invoice__student__school=school, paid_at__gte=six_months_ago)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount_kes'))
        .order_by('month')
    )

    totals_by_month = {
        row['month'].strftime('%Y-%m'): float(row['total'] or 0)
        for row in monthly_rows if row['month']
    }

    today = timezone.now().replace(day=1)
    chart_labels = []
    chart_values = []
    for i in range(5, -1, -1):
        m = (today - timedelta(days=30 * i))
        key = m.strftime('%Y-%m')
        chart_labels.append(m.strftime('%b'))
        chart_values.append(totals_by_month.get(key, 0))

    # ---------- Top 5 debtors (biggest outstanding balances) ----------
    top_debtors = (
        Student.objects
        .filter(school=school, is_active=True, invoices__isnull=False)
        .annotate(
            total_due=Sum('invoices__amount_due'),
            total_paid=Sum('invoices__amount_paid'),
        )
        .annotate(balance=F('total_due') - F('total_paid'))
        .filter(balance__gt=0)
        .order_by('-balance')[:5]
    )
        # ---------- Payment method breakdown (this month) ----------
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    method_rows = (
        Payment.objects
        .filter(
            invoice__student__school=school,
            paid_at__gte=month_start,
        )
        .values('method')
        .annotate(total=Sum('amount_kes'))
        .order_by('-total')
    )

    method_labels = dict(Payment.Method.choices)
    method_total = sum(float(r['total'] or 0) for r in method_rows)

    method_breakdown = []
    for r in method_rows:
        total = float(r['total'] or 0)
        method_breakdown.append({
            'code': r['method'],
            'label': method_labels.get(r['method'], r['method']),
            'total': total,
            'pct': round((total / method_total) * 100, 1) if method_total else 0,
        })

    return render(request, 'dashboard/accountant.html', {
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'invoice_count': invoice_count,
        'overdue_count': overdue_count,
        'unpaid_count': unpaid_count,
        'collection_rate': collection_rate,
        'recent_payments': recent_payments,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'top_debtors': top_debtors,
        'method_breakdown': method_breakdown,
        'method_total': method_total,
    })


@login_required
def accountant_invoices(request):
    """Invoice list with status tabs, search, filters, and pagination."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, FeeStructure
    from apps.students.models import Student
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    school = request.user.school

    base_qs = Invoice.objects.filter(
        student__school=school
    ).select_related('student', 'fee_structure')

    # ---------- Stats (unfiltered) ----------
    stats_agg = base_qs.aggregate(
        total=Count('id'),
        paid=Count('id', filter=Q(status='paid')),
        partial=Count('id', filter=Q(status='partial')),
        unpaid=Count('id', filter=Q(status='unpaid')),
        overdue=Count('id', filter=Q(status='overdue')),
    )

    # ---------- Filters ----------
    qs = base_qs.order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    if status_filter in ('paid', 'partial', 'unpaid', 'overdue'):
        qs = qs.filter(status=status_filter)

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__middle_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__admission_number__icontains=search) |
            Q(fee_structure__name__icontains=search)
        )

    term_filter = request.GET.get('term', '').strip()
    if term_filter:
        qs = qs.filter(fee_structure__name__startswith=f"{term_filter} —")

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ---------- Term choices for filter ----------
    all_fs = FeeStructure.objects.filter(school=school).values_list('name', flat=True)
    terms = set()
    for name in all_fs:
        if ' — ' in name:
            terms.add(name.split(' — ', 1)[0])
        else:
            terms.add(name)
    term_choices = sorted(terms)

    return render(request, 'dashboard/accountant_invoices.html', {
        'invoices': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats_agg,
        'status_filter': status_filter,
        'search': search,
        'term_filter': term_filter,
        'term_choices': term_choices,
        'total_filtered': qs.count(),
    })


@login_required
def accountant_transactions(request):
    """School accountant sees all transactions, expenditure, debts, credit."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment, Expenditure
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from datetime import date, timedelta
    from django.db.models import Sum, F

    user = request.user
    school = user.school

    # ---------- Period selection ----------
    period = request.GET.get('period', 'month')
    today = date.today()

    if period == 'month':
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')
    elif period == 'term':
        start_date = today - timedelta(days=90)
        end_date = today
        period_label = 'Last 90 days'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = str(today.year)
    elif period == 'custom':
        try:
            start_date = date.fromisoformat(request.GET.get('start', ''))
            end_date = date.fromisoformat(request.GET.get('end', ''))
        except (ValueError, TypeError):
            start_date = today.replace(day=1)
            end_date = today
        period_label = f'{start_date.strftime("%d %b %Y")} to {end_date.strftime("%d %b %Y")}'
    else:
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')

    # ---------- Fee Collections ----------
    payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date,
    ).select_related('invoice__student')

    total_collected = float(
        payments.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Breakdown by method
    method_breakdown = {}
    for row in payments.values('method').annotate(t=Sum('amount_kes')):
        label = dict(Payment.Method.choices).get(row['method'], row['method'])
        method_breakdown[label] = float(row['t'] or 0)

    # ---------- Expenditure ----------
    expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=start_date,
        spent_on__lte=end_date,
    )

    total_expenditure = float(
        expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Breakdown by category
    category_breakdown = {}
    for row in expenditures.values('category').annotate(t=Sum('amount_kes')):
        label = dict(Expenditure.Category.choices).get(row['category'], row['category'])
        category_breakdown[label] = float(row['t'] or 0)

    # ---------- Debtors ----------
    outstanding_agg = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))

    total_debts = float(outstanding_agg['t'] or 0)

    debt_count = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).values('student_id').distinct().count()

    # ---------- Net Position ----------
    net_position = total_collected - total_expenditure

    # ---------- Previous period comparison ----------
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    prev_payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=prev_start,
        paid_at__date__lte=prev_end,
    )
    prev_collected = float(
        prev_payments.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    prev_expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=prev_start,
        spent_on__lte=prev_end,
    )
    prev_expenditure = float(
        prev_expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    # Comparison helper
    def delta(curr, prev):
        curr = float(curr or 0)
        prev = float(prev or 0)
        if prev == 0:
            pct = 100 if curr > 0 else 0
            return {
                'pct': pct,
                'abs': curr - prev,
                'direction': 'up' if curr > prev else ('down' if curr < prev else 'flat'),
            }
        pct = round(((curr - prev) / prev) * 100, 1)
        return {
            'pct': pct,
            'abs': curr - prev,
            'direction': 'up' if pct > 0 else ('down' if pct < 0 else 'flat'),
        }

    collected_delta = delta(total_collected, prev_collected)
    expenditure_delta = delta(total_expenditure, prev_expenditure)
    net_delta = delta(net_position, prev_collected - prev_expenditure)

    # ---------- Per-class collection breakdown ----------
    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_student_ids = list(
            Student.objects.filter(
                school=school, class_level=cls.name, is_active=True
            ).values_list('id', flat=True)
        )
        if not class_student_ids:
            continue

        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_student_ids,
                paid_at__date__gte=start_date,
                paid_at__date__lte=end_date,
            ).aggregate(t=Sum('amount_kes'))['t'] or 0
        )

        class_outstanding = float(
            Invoice.objects.filter(
                student_id__in=class_student_ids,
                status__in=['unpaid', 'partial', 'overdue'],
            ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))['t'] or 0
        )

        class_breakdown.append({
            'class_name': cls.name,
            'students': len(class_student_ids),
            'collected': class_collected,
            'outstanding': class_outstanding,
        })

    class_breakdown.sort(key=lambda x: x['collected'], reverse=True)

    # ---------- Recent transactions (for table at bottom) ----------
    recent_payments = payments.select_related('invoice__student').order_by('-paid_at')[:20]

    # ---------- Render ----------
    return render(request, 'dashboard/accountant_transactions.html', {
        'period': period,
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'start_date_iso': start_date.isoformat(),
        'end_date_iso': end_date.isoformat(),

        # Summary
        'total_collected': total_collected,
        'total_expenditure': total_expenditure,
        'total_debts': total_debts,
        'debt_count': debt_count,
        'net_position': net_position,

        # Breakdowns
        'method_breakdown': method_breakdown,
        'category_breakdown': category_breakdown,
        'class_breakdown': class_breakdown,

        # Comparison
        'prev_collected': prev_collected,
        'prev_expenditure': prev_expenditure,
        'prev_start': prev_start,
        'prev_end': prev_end,
        'collected_delta': collected_delta,
        'expenditure_delta': expenditure_delta,
        'net_delta': net_delta,

        # Recent
        'recent_payments': recent_payments,
    })


@login_required
@login_required
def accountant_students(request):
    """List all students with their fee balances for the accountant."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel
    from django.db.models import Sum, Q

    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    school = request.user.school

    # Filters
    search = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '')
    status_filter = request.GET.get('status', '').strip()

    # ---------- All students ----------
    students_qs = Student.objects.filter(
        school=school, is_active=True
    ).order_by('class_level', 'first_name', 'last_name')

    if search:
        students_qs = students_qs.filter(
            Q(first_name__icontains=search) |
            Q(middle_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search) |
            Q(upi__icontains=search)
        )

    if class_id:
        try:
            cls = ClassLevel.objects.get(id=class_id, school=school)
            students_qs = students_qs.filter(class_level=cls.name)
        except ClassLevel.DoesNotExist:
            pass

    # ---------- Batch invoice totals (much faster than per-student loop) ----------
    student_ids = list(students_qs.values_list('id', flat=True))

    invoice_totals = (
        Invoice.objects
        .filter(student_id__in=student_ids)
        .values('student_id')
        .annotate(
            inv=Sum('amount_due'),
            pd=Sum('amount_paid'),
        )
    )
    invoice_map = {
        row['student_id']: {
            'invoiced': float(row['inv'] or 0),
            'paid': float(row['pd'] or 0),
        }
        for row in invoice_totals
    }

    # ---------- Build student rows ----------
    student_list = []
    grand_invoiced = 0
    grand_paid = 0

    for s in students_qs:
        totals = invoice_map.get(s.id, {'invoiced': 0, 'paid': 0})
        total_invoiced = totals['invoiced']
        total_paid = totals['paid']
        balance = total_invoiced - total_paid

        # Determine status
        if total_invoiced == 0:
            status = 'none'
        elif balance <= 0:
            status = 'paid'
        elif total_paid > 0:
            status = 'partial'
        else:
            status = 'unpaid'

        # Apply status filter
        if status_filter and status != status_filter:
            continue

        student_list.append({
            'student': s,
            'invoiced': total_invoiced,
            'paid': total_paid,
            'balance': balance,
            'status': status,
        })

        grand_invoiced += total_invoiced
        grand_paid += total_paid

    grand_balance = grand_invoiced - grand_paid

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    return render(request, 'dashboard/accountant_students.html', {
        'students_data': student_list,
        'total_students': len(student_list),
        'grand_invoiced': grand_invoiced,
        'grand_paid': grand_paid,
        'grand_balance': grand_balance,
        'classes': classes,
        'search': search,
        'class_id': class_id,
        'status_filter': status_filter,
    })


@login_required
def generate_invoices(request):
    """
    Generate invoices in 3 modes:
      - Single student (custom or class-default amount)
      - Single class (all active students)
      - All classes (bulk by term)
    """
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import FeeStructure, Invoice
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from django.db import transaction
    from collections import defaultdict
    from decimal import Decimal

    school = request.user.school

    # ---- Group fee structures by term ----
    all_fs = FeeStructure.objects.filter(school=school).order_by('name')
    terms = defaultdict(list)
    for fs in all_fs:
        term_part = fs.name.split(' — ', 1)[0] if ' — ' in fs.name else fs.name
        terms[term_part].append(fs)
    term_choices = sorted(terms.keys())

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # ---- Helper: compute total fee for a class + term ----
    def class_term_total(class_name, term_prefix):
        qs = FeeStructure.objects.filter(
            school=school,
            class_level=class_name,
            name__startswith=f"{term_prefix} —",
        )
        if not qs.exists():
            return None, None, None
        total = sum(float(f.amount_kes) for f in qs)
        anchor = qs.first()
        return float(total), anchor, anchor.due_date

    # ==========================================================
    # POST — do the generation
    # ==========================================================
    if request.method == 'POST':
        mode = request.POST.get('mode', 'bulk')
        term_name = request.POST.get('term', '').strip()
        custom_term = request.POST.get('custom_term', '').strip()
        term_prefix = custom_term or term_name

        if not term_prefix:
            messages.error(request, 'Please select or type a term.')
            return redirect('generate_invoices')

        # ---------------------------------------------------
        # MODE: SINGLE STUDENT
        # ---------------------------------------------------
        if mode == 'single':
            student_id = request.POST.get('student_id')
            custom_amount = request.POST.get('custom_amount', '').strip()
            override_amount = request.POST.get('override_amount', '').strip()

            try:
                student = Student.objects.get(
                    id=student_id, school=school, is_active=True
                )
            except Student.DoesNotExist:
                messages.error(request, 'Student not found.')
                return redirect('generate_invoices')

            # Determine amount
            if override_amount and custom_amount:
                # Custom amount from modal
                try:
                    amount = float(custom_amount)
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid custom amount.')
                    return redirect('generate_invoices')
                # Use first matching FS as anchor if available
                anchor = FeeStructure.objects.filter(
                    school=school, class_level=student.class_level,
                    name__startswith=f"{term_prefix} —"
                ).first()
                if not anchor:
                    messages.error(
                        request,
                        f'No fee structure exists for {student.class_level} — '
                        f'please use matrix draft first.'
                    )
                    return redirect('generate_invoices')
                due_date = anchor.due_date
            else:
                # Use class default
                amount, anchor, due_date = class_term_total(
                    student.class_level, term_prefix
                )
                if amount is None:
                    messages.error(
                        request,
                        f'No fee structure for {student.class_level} '
                        f'in term "{term_prefix}".'
                    )
                    return redirect('generate_invoices')

            invoice, created = Invoice.objects.get_or_create(
                student=student,
                fee_structure=anchor,
                defaults={'amount_due': amount, 'due_date': due_date},
            )
            if created:
                messages.success(
                    request,
                    f'✅ Invoice created for {student.full_name}: '
                    f'KES {amount:,.0f} ({term_prefix}).'
                )
            else:
                invoice.amount_due = amount
                invoice.due_date = due_date
                invoice.save(update_fields=['amount_due', 'due_date'])
                invoice.update_status()
                messages.info(
                    request,
                    f'Invoice updated for {student.full_name}: '
                    f'KES {amount:,.0f}.'
                )
            return redirect('accountant_invoices')

        # ---------------------------------------------------
        # MODE: SINGLE CLASS
        # ---------------------------------------------------
        if mode == 'class':
            class_name = request.POST.get('class_name', '').strip()
            if not class_name:
                messages.error(request, 'Please pick a class.')
                return redirect('generate_invoices')

            amount, anchor, due_date = class_term_total(class_name, term_prefix)
            if amount is None:
                messages.error(
                    request,
                    f'No fee structure for {class_name} in "{term_prefix}".'
                )
                return redirect('generate_invoices')

            students = Student.objects.filter(
                school=school, class_level=class_name, is_active=True,
            )

            created_count = 0
            updated_count = 0
            total_billed = 0

            with transaction.atomic():
                for s in students:
                    inv, was_created = Invoice.objects.get_or_create(
                        student=s,
                        fee_structure=anchor,
                        defaults={'amount_due': amount, 'due_date': due_date},
                    )
                    if was_created:
                        created_count += 1
                        total_billed += amount
                    elif float(inv.amount_due) != amount:
                        inv.amount_due = amount
                        inv.due_date = due_date
                        inv.save(update_fields=['amount_due', 'due_date'])
                        inv.update_status()
                        updated_count += 1

            msg = f'✅ {class_name} ({term_prefix}): {created_count} created'
            if updated_count:
                msg += f', {updated_count} updated'
            msg += f'. Total billed: KES {total_billed:,.0f}.'
            messages.success(request, msg)
            return redirect('accountant_invoices')

        # ---------------------------------------------------
        # MODE: ALL CLASSES (bulk)
        # ---------------------------------------------------
        matching_fs = FeeStructure.objects.filter(
            school=school,
            name__startswith=f"{term_prefix} —",
        )

        if not matching_fs.exists():
            messages.error(
                request, f'No fee structures found for term "{term_prefix}".'
            )
            return redirect('generate_invoices')

        by_class = defaultdict(list)
        for fs in matching_fs:
            by_class[fs.class_level].append(fs)

        created_count = 0
        updated_count = 0
        classes_processed = 0
        total_billed = 0

        with transaction.atomic():
            for class_name, fee_list in by_class.items():
                total_fee = sum(float(f.amount_kes) for f in fee_list)
                if total_fee <= 0:
                    continue

                anchor_fs = fee_list[0]
                due_date = anchor_fs.due_date

                students = Student.objects.filter(
                    school=school, class_level=class_name, is_active=True,
                )

                for student in students:
                    inv, was_created = Invoice.objects.get_or_create(
                        student=student,
                        fee_structure=anchor_fs,
                        defaults={'amount_due': total_fee, 'due_date': due_date},
                    )
                    if was_created:
                        created_count += 1
                        total_billed += total_fee
                    elif float(inv.amount_due) != total_fee:
                        inv.amount_due = total_fee
                        inv.due_date = due_date
                        inv.save(update_fields=['amount_due', 'due_date'])
                        inv.update_status()
                        updated_count += 1

                classes_processed += 1

        msg = f'✅ Bulk ({term_prefix}): {created_count} created'
        if updated_count:
            msg += f', {updated_count} updated'
        msg += f' across {classes_processed} classes.'
        messages.success(request, msg)
        return redirect('accountant_invoices')

    # ==========================================================
    # GET — render form + optional preview
    # ==========================================================
    preview_term = request.GET.get('term', '').strip()

    preview = None
    if preview_term:
        matching = FeeStructure.objects.filter(
            school=school, name__startswith=f"{preview_term} —"
        )
        by_class = defaultdict(lambda: {'items': [], 'total': 0.0, 'due_date': None})
        for fs in matching:
            by_class[fs.class_level]['items'].append({
                'name': fs.name.split(' — ', 1)[-1] if ' — ' in fs.name else fs.name,
                'amount': float(fs.amount_kes),
            })
            by_class[fs.class_level]['total'] += float(fs.amount_kes)
            if not by_class[fs.class_level]['due_date']:
                by_class[fs.class_level]['due_date'] = fs.due_date

        preview_classes = []
        grand_total = 0
        total_students = 0
        for class_name, data in by_class.items():
            count = Student.objects.filter(
                school=school, class_level=class_name, is_active=True
            ).count()
            if count == 0:
                continue
            class_total = data['total'] * count
            grand_total += class_total
            total_students += count
            preview_classes.append({
                'class_name': class_name,
                'items': data['items'],
                'per_student': data['total'],
                'student_count': count,
                'class_total': class_total,
                'due_date': data['due_date'],
            })
        preview_classes.sort(key=lambda x: x['class_name'])

        preview = {
            'term': preview_term,
            'classes': preview_classes,
            'total_students': total_students,
            'grand_total': grand_total,
        }

       # Students for single-student dropdown
    all_students = Student.objects.filter(
        school=school, is_active=True
    ).order_by('class_level', 'first_name', 'last_name')

    return render(request, 'dashboard/generate_invoices.html', {
        'term_choices': term_choices,
        'classes': classes,
        'students': all_students,
        'preview': preview,
        'preview_term': preview_term,
    })


@login_required
def invoice_student_quick(request, student_id):
    """Quick-invoice a single student from the Students & Fees page."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.finance.models import FeeStructure, Invoice
    from collections import defaultdict

    school = request.user.school
    student = get_object_or_404(Student, id=student_id, school=school)

    # Get available terms for the student's class
    fs_qs = FeeStructure.objects.filter(
        school=school, class_level=student.class_level
    ).order_by('name')

    terms = defaultdict(lambda: {'total': 0.0, 'anchor': None})
    for fs in fs_qs:
        term_part = fs.name.split(' — ', 1)[0] if ' — ' in fs.name else fs.name
        terms[term_part]['total'] += float(fs.amount_kes)
        if terms[term_part]['anchor'] is None:
            terms[term_part]['anchor'] = fs

    term_options = [
        {'name': t, 'total': d['total'], 'anchor_id': d['anchor'].id if d['anchor'] else None}
        for t, d in sorted(terms.items())
    ]

    if request.method == 'POST':
        term_name = request.POST.get('term', '').strip()
        custom_amount = request.POST.get('custom_amount', '').strip()
        override = request.POST.get('override', '') == '1'

        if not term_name:
            messages.error(request, 'Please pick a term.')
            return redirect('invoice_student_quick', student_id=student.id)

        # Determine anchor
        term_fs = fs_qs.filter(name__startswith=f"{term_name} —")
        if not term_fs.exists():
            messages.error(request, f'No fees for "{term_name}".')
            return redirect('invoice_student_quick', student_id=student.id)
        anchor = term_fs.first()

        # Determine amount
        if override and custom_amount:
            try:
                amount = float(custom_amount)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'Invalid custom amount.')
                return redirect('invoice_student_quick', student_id=student.id)
        else:
            amount = sum(float(f.amount_kes) for f in term_fs)

        invoice, created = Invoice.objects.get_or_create(
            student=student,
            fee_structure=anchor,
            defaults={'amount_due': amount, 'due_date': anchor.due_date},
        )
        if created:
            messages.success(
                request,
                f'✅ Invoice created for {student.full_name}: KES {amount:,.0f}.'
            )
        else:
            invoice.amount_due = amount
            invoice.due_date = anchor.due_date
            invoice.save(update_fields=['amount_due', 'due_date'])
            invoice.update_status()
            messages.info(request, f'Invoice updated: KES {amount:,.0f}.')
        return redirect('accountant_students')
    return render(request, 'dashboard/invoice_student_quick.html', {
        'student': student,
        'term_options': term_options,
    })


@login_required
def record_payment(request, invoice_id):
    """Record a manual payment against an invoice."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment

    invoice = get_object_or_404(
        Invoice, id=invoice_id, student__school=request.user.school
    )

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        method = request.POST.get('method', 'cash')
        external_ref = request.POST.get('external_reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []

        try:
            amount = float(amount)
            if amount <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Please enter a valid amount.')
            amount = 0

        if method not in [c[0] for c in Payment.Method.choices]:
            errors.append('Invalid payment method.')

        if method in ('mpesa', 'airtel', 'bank', 'cheque') and not external_ref:
            errors.append(f'Please enter the {method.upper()} transaction reference.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('record_payment', invoice_id=invoice.id)

        try:
            payment = Payment.objects.create(
                invoice=invoice,
                amount_kes=amount,
                method=method,
                external_reference=external_ref,
                notes=notes,
                recorded_by=request.user,
            )
            messages.success(
                request,
                f'Payment recorded. Transaction: {payment.reference} '
                f'(KES {amount:,.2f} via {payment.get_method_display()})'
            )
            return redirect('accountant_invoices')
        except Exception as e:
            messages.error(request, f'Error recording payment: {e}')
            return redirect('record_payment', invoice_id=invoice.id)

    # GET — render form
    return render(request, 'dashboard/record_payment.html', {
        'invoice': invoice,
        'methods': Payment.Method.choices,
    })


@login_required
def financial_report_pdf(request):
    """Generate a financial report PDF for the selected period."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import Invoice, Payment, Expenditure
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from django.db.models import Sum, F
    from django.utils import timezone
    from datetime import date, timedelta
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    school = user.school
    today = date.today()

    # ---------- Period selection ----------
    period = request.GET.get('period', 'month')
    if period == 'custom':
        try:
            start_date = date.fromisoformat(request.GET.get('start', ''))
            end_date = date.fromisoformat(request.GET.get('end', ''))
        except (ValueError, TypeError):
            start_date = today.replace(day=1)
            end_date = today
        period_label = f'{start_date.strftime("%d %b %Y")} — {end_date.strftime("%d %b %Y")}'
    elif period == 'term':
        start_date = today - timedelta(days=90)
        end_date = today
        period_label = 'Last 90 Days'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_label = f'Year {today.year}'
    else:
        start_date = today.replace(day=1)
        end_date = today
        period_label = today.strftime('%B %Y')

    # ---------- Collections ----------
    payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=start_date,
        paid_at__date__lte=end_date,
    ).select_related('invoice__student')

    total_collected = float(payments.aggregate(t=Sum('amount_kes'))['t'] or 0)

    method_breakdown = {}
    for row in payments.values('method').annotate(t=Sum('amount_kes')):
        label = dict(Payment.Method.choices).get(row['method'], row['method'])
        method_breakdown[label] = float(row['t'] or 0)

    # ---------- Expenditure ----------
    expenditures = Expenditure.objects.filter(
        school=school,
        spent_on__gte=start_date,
        spent_on__lte=end_date,
    )
    total_expenditure = float(expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0)

    category_breakdown = {}
    for row in expenditures.values('category').annotate(t=Sum('amount_kes')):
        label = dict(Expenditure.Category.choices).get(row['category'], row['category'])
        category_breakdown[label] = float(row['t'] or 0)

    net_position = total_collected - total_expenditure

    # ---------- Outstanding ----------
    outstanding_agg = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))
    total_outstanding = float(outstanding_agg['t'] or 0)

    # ---------- Per-class breakdown ----------
    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_students = list(
            Student.objects.filter(
                school=school, class_level=cls.name, is_active=True
            ).values_list('id', flat=True)
        )
        if not class_students:
            continue

        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_students,
                paid_at__date__gte=start_date,
                paid_at__date__lte=end_date,
            ).aggregate(t=Sum('amount_kes'))['t'] or 0
        )

        class_breakdown.append({
            'class_name': cls.name,
            'students': len(class_students),
            'collected': class_collected,
        })

    class_breakdown.sort(key=lambda x: x['collected'], reverse=True)

    # ---------- Previous period ----------
    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    prev_collected = float(
        Payment.objects.filter(
            invoice__student__school=school,
            paid_at__date__gte=prev_start,
            paid_at__date__lte=prev_end,
        ).aggregate(t=Sum('amount_kes'))['t'] or 0
    )
    prev_expenditure = float(
        Expenditure.objects.filter(
            school=school, spent_on__gte=prev_start, spent_on__lte=prev_end,
        ).aggregate(t=Sum('amount_kes'))['t'] or 0
    )

    html_string = render_to_string('pdf/financial_report.html',
        build_pdf_context(
            school=school,
            generated_by=user,
            period_label=period_label,
            start_date=start_date,
            end_date=end_date,
            prev_start=prev_start,
            prev_end=prev_end,
            total_collected=total_collected,
            total_expenditure=total_expenditure,
            total_outstanding=total_outstanding,
            net_position=net_position,
            prev_collected=prev_collected,
            prev_expenditure=prev_expenditure,
            method_breakdown=method_breakdown,
            category_breakdown=category_breakdown,
            class_breakdown=class_breakdown,
        )
    )

    filename = f'financial_report_{start_date.isoformat()}_{end_date.isoformat()}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
@role_required('accountant', 'principal')
def class_fee_statement(request):
    """Shows fee summary for one class + per-student breakdown."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # ---------- Class selector ----------
    class_id = request.GET.get('class')
    if not class_id and classes.exists():
        class_id = classes.first().id

    selected_class = None
    if class_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
        except ClassLevel.DoesNotExist:
            pass

    # ---------- Search + Status filter ----------
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    # ---------- Students + invoices ----------
    students_data = []
    class_invoiced = 0
    class_paid = 0
    counts = {'paid': 0, 'partial': 0, 'unpaid': 0, 'overdue': 0, 'none': 0}

    if selected_class:
        students_qs = Student.objects.filter(
            school=school,
            class_level=selected_class.name,
            is_active=True,
        ).order_by('first_name', 'last_name')

        if search:
            students_qs = students_qs.filter(
                models.Q(first_name__icontains=search) |
                models.Q(middle_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(admission_number__icontains=search)
            )

        for s in students_qs:
            invoices = Invoice.objects.filter(student=s)
            total_invoiced = sum(i.amount_due for i in invoices) or 0
            total_paid = sum(i.amount_paid for i in invoices) or 0
            balance = total_invoiced - total_paid

            if total_invoiced == 0:
                status = 'none'
            elif balance <= 0:
                status = 'paid'
            elif any(i.status == 'overdue' for i in invoices):
                status = 'overdue'
            elif total_paid > 0:
                status = 'partial'
            else:
                status = 'unpaid'

            counts[status] = counts.get(status, 0) + 1

            # Apply status filter
            if status_filter and status != status_filter:
                continue

            students_data.append({
                'student': s,
                'invoiced': total_invoiced,
                'paid': total_paid,
                'balance': balance,
                'status': status,
                'invoice_count': invoices.count(),
            })

            class_invoiced += total_invoiced
            class_paid += total_paid

    class_balance = class_invoiced - class_paid

    return render(request, 'dashboard/class_fee_statement.html', {
        'classes': classes,
        'selected_class': selected_class,
        'students_data': students_data,
        'total_students': len(students_data),
        'class_invoiced': class_invoiced,
        'class_paid': class_paid,
        'class_balance': class_balance,
        'counts': counts,
        'search': search,
        'status_filter': status_filter,
    })


@login_required
@role_required('accountant', 'principal')
def class_fee_statement_pdf(request, class_id):
    """Generate PDF of class fee statement (A4 landscape)."""
    from apps.students.models import Student
    from apps.finance.models import Invoice
    from apps.academics.models import ClassLevel
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school

    try:
        selected_class = ClassLevel.objects.get(id=class_id, school=school)
    except ClassLevel.DoesNotExist:
        messages.error(request, 'Class not found.')
        return redirect('class_fee_statement')

    students = Student.objects.filter(
        school=school,
        class_level=selected_class.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    students_data = []
    class_invoiced = 0
    class_paid = 0

    for s in students:
        invoices = Invoice.objects.filter(student=s)
        total_invoiced = sum(i.amount_due for i in invoices) or 0
        total_paid = sum(i.amount_paid for i in invoices) or 0
        balance = total_invoiced - total_paid

        if total_invoiced == 0:
            status = 'none'
        elif balance <= 0:
            status = 'paid'
        elif total_paid > 0:
            status = 'partial'
        else:
            status = 'unpaid'

        students_data.append({
            'student': s,
            'invoiced': total_invoiced,
            'paid': total_paid,
            'balance': balance,
            'status': status,
        })

        class_invoiced += total_invoiced
        class_paid += total_paid

    class_balance = class_invoiced - class_paid

    html_string = render_to_string('pdf/class_fee_statement.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            selected_class=selected_class,
            students_data=students_data,
            total_students=len(students_data),
            class_invoiced=class_invoiced,
            class_paid=class_paid,
            class_balance=class_balance,
            printed_by=request.user,
        )
    )

    filename = f'class_statement_{selected_class.name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
@role_required('accountant', 'principal')
def fee_structure_list(request):
    """List all fee structures with filters and summary."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel
    from django.db.models import Sum
    from collections import defaultdict

    school = request.user.school
    qs = FeeStructure.objects.filter(school=school).order_by('-created_at')

    # ---------- Filters ----------
    class_filter = request.GET.get('class', '').strip()
    term_filter = request.GET.get('term', '').strip()
    search = request.GET.get('q', '').strip()

    if class_filter:
        qs = qs.filter(class_level=class_filter)
    if term_filter:
        qs = qs.filter(name__startswith=f"{term_filter} —")
    if search:
        qs = qs.filter(name__icontains=search)

    # ---------- Summary ----------
    total_value = qs.aggregate(t=Sum('amount_kes'))['t'] or 0

    # ---------- Distinct classes used ----------
    all_school_fs = FeeStructure.objects.filter(school=school)
    used_classes = sorted(set(
        all_school_fs.values_list('class_level', flat=True)
    ))

    # ---------- Term choices ----------
    terms = set()
    for name in all_school_fs.values_list('name', flat=True):
        if ' — ' in name:
            terms.add(name.split(' — ', 1)[0])
        else:
            terms.add(name)
    term_choices = sorted(terms)

    # ---------- Group by term for display ----------
    grouped = defaultdict(list)
    for fs in qs:
        if ' — ' in fs.name:
            term = fs.name.split(' — ', 1)[0]
        else:
            term = 'Uncategorized'
        grouped[term].append(fs)

    # Sort terms and get ordered groups
    grouped_list = sorted(
        grouped.items(),
        key=lambda x: x[0],
        reverse=True
    )

    return render(request, 'dashboard/fee_structure_list.html', {
        'fee_structures': qs,
        'count': qs.count(),
        'total_value': total_value,
        'used_classes': used_classes,
        'term_choices': term_choices,
        'class_filter': class_filter,
        'term_filter': term_filter,
        'search': search,
        'grouped_list': grouped_list,
        'all_classes': ClassLevel.objects.filter(school=school).order_by('order', 'name'),
    })


@login_required
@role_required('accountant', 'principal')
def fee_structure_add(request):
    """Create a new fee structure."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        class_level = request.POST.get('class_level', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None

        errors = []
        if not name: errors.append('Name is required.')
        if not class_level: errors.append('Class is required.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not due_date: errors.append('Due date is required.')

        if errors:
            for e in errors: messages.error(request, e)
            return render(request, 'dashboard/fee_structure_form.html', {
                'classes': classes,
                'action': 'add',
                'form_data': request.POST,
            })

        FeeStructure.objects.create(
            school=school,
            name=name,
            class_level=class_level,
            amount_kes=amount,
            due_date=due_date,
        )
        messages.success(request, f'✅ Fee structure "{name}" created for {class_level}.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {
        'classes': classes,
        'action': 'add',
    })


@login_required
@role_required('accountant', 'principal')
def fee_structure_edit(request, fee_id):
    """Edit an existing fee structure."""
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    fs = get_object_or_404(FeeStructure, id=fee_id, school=school)
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        fs.name = request.POST.get('name', fs.name).strip()
        fs.class_level = request.POST.get('class_level', fs.class_level).strip()
        fs.due_date = request.POST.get('due_date') or fs.due_date

        try:
            fs.amount_kes = float(request.POST.get('amount_kes', fs.amount_kes))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('fee_structure_edit', fee_id=fs.id)

        fs.save()
        messages.success(request, f'✅ Fee structure "{fs.name}" updated.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {
        'classes': classes,
        'fee_structure': fs,
        'action': 'edit',
    })


@login_required
@role_required('accountant', 'principal')
def fee_structure_delete(request, fee_id):
    """Delete a fee structure."""
    from apps.finance.models import FeeStructure

    fs = get_object_or_404(FeeStructure, id=fee_id, school=request.user.school)

    if request.method == 'POST':
        name = fs.name
        fs.delete()
        messages.success(request, f'🗑️ Fee structure "{name}" deleted.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_delete.html', {'fee_structure': fs})


@login_required
@role_required('accountant', 'principal')
def fee_structure_bulk(request):
    """
    Bulk-draft fee structures across ALL classes.

    The user enters a fee name, amount, and due date, and selects which classes
    should receive this fee. All selected classes get a FeeStructure created
    with the same amount.
    """
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None
        selected_class_ids = request.POST.getlist('classes')  # list of class IDs
        skip_existing = request.POST.get('skip_existing') == 'on'

        errors = []
        if not name: errors.append('Fee name is required.')
        if not selected_class_ids: errors.append('Select at least one class.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not due_date: errors.append('Due date is required.')

        if errors:
            for e in errors: messages.error(request, e)
            return render(request, 'dashboard/fee_structure_bulk.html', {
                'classes': classes,
                'form_data': request.POST,
            })

        created = 0
        skipped = 0

        for class_id in selected_class_ids:
            try:
                cls = ClassLevel.objects.get(id=class_id, school=school)
            except ClassLevel.DoesNotExist:
                continue

            # Check for existing fee with same name + class
            exists = FeeStructure.objects.filter(
                school=school,
                name=name,
                class_level=cls.name,
            ).exists()

            if exists and skip_existing:
                skipped += 1
                continue

            FeeStructure.objects.create(
                school=school,
                name=name,
                class_level=cls.name,
                amount_kes=amount,
                due_date=due_date,
            )
            created += 1

        messages.success(
            request,
            f'✅ Created {created} fee structure{{created|pluralize}}'
            + (f' · Skipped {skipped} duplicate{{skipped|pluralize}}' if skipped else '')
            + '.'
        )
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_bulk.html', {
        'classes': classes,
    })


@login_required
def fee_structure_matrix(request):
    """Bulk draft page — matrix editor for fee items × classes."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    import json
    from django.utils import timezone
    from datetime import timedelta
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    classes_json = json.dumps([
        {'id': c.id, 'name': c.name} for c in classes
    ])

    # Default term name suggestion
    today = timezone.now().date()
    year = today.year
    default_term_name = f"Term {((today.month - 1) // 4) + 1} {year}"

    # Default due date = 30 days from now
    default_due_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')

    return render(request, 'dashboard/fee_structure_matrix.html', {
        'classes_json': classes_json,
        'default_term_name': default_term_name,
        'default_due_date': default_due_date,
    })


@login_required
def fee_structure_matrix_save(request):
    """Receives the matrix JSON and creates FeeStructure rows."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    if request.user.role not in ('accountant', 'principal'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    import json
    from django.db import transaction
    from datetime import datetime
    from apps.finance.models import FeeStructure
    from apps.academics.models import ClassLevel

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    term_name = (payload.get('term_name') or '').strip()
    due_date_str = (payload.get('due_date') or '').strip()
    rows = payload.get('rows') or []

    if not term_name:
        return JsonResponse({'success': False, 'error': 'Term name is required'}, status=400)

    if not due_date_str:
        return JsonResponse({'success': False, 'error': 'Due date is required'}, status=400)

    try:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)

    if not rows:
        return JsonResponse({'success': False, 'error': 'No fee items provided'}, status=400)

    school = request.user.school

    # Validate class IDs belong to this school
    valid_class_ids = set(
        ClassLevel.objects.filter(school=school).values_list('id', flat=True)
    )

    created = 0
    updated = 0

    try:
        with transaction.atomic():
            for row in rows:
                item_name = (row.get('name') or '').strip()
                if not item_name:
                    continue

                amounts = row.get('amounts') or {}
                full_name = f"{term_name} — {item_name}"

                for cls_id_str, amount in amounts.items():
                    try:
                        cls_id = int(cls_id_str)
                        amount_val = float(amount) if amount not in (None, '') else 0
                    except (ValueError, TypeError):
                        continue

                    if amount_val <= 0:
                        continue
                    if cls_id not in valid_class_ids:
                        continue

                    cls = ClassLevel.objects.get(id=cls_id)

                    obj, was_created = FeeStructure.objects.update_or_create(
                        school=school,
                        name=full_name,
                        class_level=cls.name,
                        defaults={
                            'amount_kes': amount_val,
                            'due_date': due_date,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({
        'success': True,
        'created': created,
        'updated': updated,
        'message': f'{created} created, {updated} updated.',
    })


@login_required
def fee_structure_class_pdf(request, class_name):
    """Print/download the fee structure for ONE class as A4 portrait PDF."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from django.utils import timezone
    from urllib.parse import unquote
    from apps.finance.models import FeeStructure
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from urllib.parse import unquote
    class_name = unquote(class_name).strip()

    school = request.user.school
    class_name = unquote(class_name).strip()
    term_filter = request.GET.get('term', '').strip()

    # Fetch fee structures for THIS class only
    qs = FeeStructure.objects.filter(
        school=school,
        class_level=class_name,
    ).order_by('name')

    if term_filter:
        qs = qs.filter(name__startswith=f"{term_filter} —")

    if not qs.exists():
        return HttpResponse(
            f'<h1>No fee structure found for {class_name}</h1>'
            '<p>Draft fees for this class first.</p>',
            status=404
        )

    # Group by term prefix
    terms = set()
    items = []  # list of (item_name, amount)
    due_date = None
    total = 0

    for fs in qs:
        if ' — ' in fs.name:
            term_part, item_part = fs.name.split(' — ', 1)
            terms.add(term_part)
        else:
            term_part = fs.name
            item_part = fs.name
            terms.add(term_part)

        items.append((item_part, float(fs.amount_kes)))
        total += float(fs.amount_kes)
        if due_date is None:
            due_date = fs.due_date

    term_name = term_filter if term_filter else (sorted(terms)[-1] if terms else 'Fee Structure')

    # Logo path (Option A — file path)
    school_logo_path = ''
    if school.logo and hasattr(school.logo, 'path'):
        try:
            school_logo_path = school.logo.path
        except (ValueError, NotImplementedError):
            school_logo_path = ''

    html_string = render_to_string('pdf/fee_structure.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            school_logo_path=school_logo_path,
            term_name=term_name,
            due_date=due_date,
            class_name=class_name,
            classes=[{'name': class_name}],
            rows=[
                {'name': name, 'amounts': [amount], 'total': amount}
                for name, amount in sorted(items)
            ],
            column_totals=[total],
            grand_total=total,
        )
    )

    safe_class = class_name.replace(' ', '_').replace('/', '-')
    filename = f'fee_structure_{safe_class}_{term_name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
def expenditure_list(request):
    """List all expenditures with filters, pagination, and category summary."""
    from apps.finance.models import Expenditure
    from django.db.models import Sum, Count
    from django.core.paginator import Paginator
    from collections import defaultdict
    from django.utils.dateparse import parse_date

    school = request.user.school

    base_qs = Expenditure.objects.filter(
        school=school
    ).select_related('recorded_by').order_by('-spent_on', '-created_at')

    # ---------- Filters ----------
    category = request.GET.get('category', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    search = request.GET.get('q', '').strip()

    qs = base_qs

    if category:
        qs = qs.filter(category=category)

    if date_from:
        d = parse_date(date_from)
        if d:
            qs = qs.filter(spent_on__gte=d)

    if date_to:
        d = parse_date(date_to)
        if d:
            qs = qs.filter(spent_on__lte=d)

    if search:
        qs = qs.filter(
            models.Q(description__icontains=search) |
            models.Q(paid_to__icontains=search) |
            models.Q(reference__icontains=search)
        )

    # ---------- Aggregate ----------
    agg = qs.aggregate(
        total=Sum('amount_kes'),
        count=Count('id'),
    )
    total = float(agg['total'] or 0)
    count = agg['count'] or 0

    # ---------- Category breakdown ----------
    category_totals = (
        qs.values('category')
        .annotate(subtotal=Sum('amount_kes'), cnt=Count('id'))
        .order_by('-subtotal')
    )
    category_labels = dict(Expenditure.Category.choices)
    category_summary = [
        {
            'code': row['category'],
            'label': category_labels.get(row['category'], row['category']),
            'total': float(row['subtotal'] or 0),
            'count': row['cnt'],
        }
        for row in category_totals
    ]

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/expenditure_list.html', {
        'expenditures': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': total,
        'count': count,
        'categories': Expenditure.Category.choices,
        'category_summary': category_summary,
        'category_filter': category,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_add(request):
    """Add new expenditure."""
    from apps.finance.models import Expenditure

    if request.method == 'POST':
        category = request.POST.get('category', '')
        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        spent_on = request.POST.get('spent_on') or None
        paid_to = request.POST.get('paid_to', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference = request.POST.get('reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not category: errors.append('Category is required.')
        if not description: errors.append('Description is required.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not spent_on: errors.append('Date is required.')

        if errors:
            for e in errors: messages.error(request, e)
        else:
            Expenditure.objects.create(
                school=request.user.school,
                category=category, description=description,
                amount_kes=amount, spent_on=spent_on,
                paid_to=paid_to, payment_method=payment_method,
                reference=reference, notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'✅ Expenditure of KES {amount:,.2f} recorded.')
            return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices,
        'action': 'add',
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_edit(request, expenditure_id):
    """Edit existing expenditure."""
    from apps.finance.models import Expenditure

    exp = get_object_or_404(Expenditure, id=expenditure_id, school=request.user.school)

    if request.method == 'POST':
        exp.category = request.POST.get('category', exp.category)
        exp.description = request.POST.get('description', exp.description).strip()
        exp.spent_on = request.POST.get('spent_on') or exp.spent_on
        exp.paid_to = request.POST.get('paid_to', '').strip()
        exp.payment_method = request.POST.get('payment_method', exp.payment_method)
        exp.reference = request.POST.get('reference', '').strip()
        exp.notes = request.POST.get('notes', '').strip()

        try:
            exp.amount_kes = float(request.POST.get('amount_kes', exp.amount_kes))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('expenditure_edit', expenditure_id=exp.id)

        exp.save()
        messages.success(request, '✅ Expenditure updated.')
        return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices,
        'expenditure': exp,
        'action': 'edit',
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_delete(request, expenditure_id):
    """Delete expenditure."""
    from apps.finance.models import Expenditure

    exp = get_object_or_404(Expenditure, id=expenditure_id, school=request.user.school)

    if request.method == 'POST':
        desc = exp.description
        exp.delete()
        messages.success(request, f'🗑️ Expenditure "{desc}" deleted.')
        return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_delete.html', {'expenditure': exp})


@login_required
@role_required('accountant', 'principal')
def expenditure_pdf(request):
    """Generate PDF of expenditures with filters."""
    from apps.finance.models import Expenditure
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school
    qs = Expenditure.objects.filter(school=school).order_by('-spent_on')

    # Apply same filters
    category = request.GET.get('category', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if category: qs = qs.filter(category=category)
    if date_from:
        try: qs = qs.filter(spent_on__gte=date_from)
        except: pass
    if date_to:
        try: qs = qs.filter(spent_on__lte=date_to)
        except: pass

    total = sum(e.amount_kes for e in qs)

    # Group by category for summary
    category_totals = {}
    for e in qs:
        cat = e.get_category_display()
        category_totals[cat] = category_totals.get(cat, 0) + float(e.amount_kes)

    html_string = render_to_string('pdf/expenditure_statement.html',
        build_pdf_context(
            school=school,
            generated_by=request.user,
            expenditures=qs,
            total=total,
            count=qs.count(),
            category_totals=category_totals,
            category_filter=category,
            date_from=date_from,
            date_to=date_to,
            printed_by=request.user,
        )
    )

    filename = 'expenditure_statement.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
def add_expenditure(request):
    """Accountant adds an expenditure entry."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.finance.models import Expenditure

    if request.method == 'POST':
        category = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        spent_on = request.POST.get('spent_on') or None
        paid_to = request.POST.get('paid_to', '').strip()
        payment_method = request.POST.get('payment_method', 'cash')
        reference = request.POST.get('reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not category:
            errors.append('Category is required.')
        if not description:
            errors.append('Description is required.')
        try:
            amount = float(amount)
            if amount <= 0:
                errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not spent_on:
            errors.append('Date is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            Expenditure.objects.create(
                school=request.user.school,
                category=category,
                description=description,
                amount_kes=amount,
                spent_on=spent_on,
                paid_to=paid_to,
                payment_method=payment_method,
                reference=reference,
                notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'Expenditure of KES {amount:,.2f} recorded.')
            return redirect('accountant_transactions')

    return render(request, 'dashboard/add_expenditure.html', {
        'categories': Expenditure.Category.choices,
    })


