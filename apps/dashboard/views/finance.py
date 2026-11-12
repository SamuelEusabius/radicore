"""
Finance views:
- Accountant dashboard & invoices
- Fee structure management (list, add, edit, delete, bulk, matrix)
- Invoice generation & payment recording
- Expenditures (list, add, edit, delete, PDF)
- Fee statements (class-wide)
- Financial reports
"""

from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from datetime import date, datetime, timedelta
from collections import defaultdict
from decimal import Decimal

from apps.academics.models import ClassLevel
from apps.finance.models import FeeStructure, Invoice, Payment, Expenditure
from apps.students.models import Student
from apps.accounts.decorators import role_required, school_staff_only, accountant_only
from apps.core.pdf_utils import build_pdf_context
from apps.finance.mpesa_models import MpesaTransaction
from django.template.loader import render_to_string
from django.http import HttpResponse
from apps.core.pdf_utils import html_to_pdf_response, get_school_logo_data_uri
from apps.finance.models import FeeStructure

# ============================================================
# ACCOUNTANT DASHBOARD
# ============================================================

@login_required
@accountant_only
def accountant_dash(request):
    from django.db.models.functions import TruncMonth

    school = request.user.school

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
        (float(total_paid) / float(total_invoiced) * 100) if total_invoiced else 0, 1
    )

    status_counts = dict(invoice_qs.values_list('status').annotate(c=Count('id')))
    overdue_count = status_counts.get('overdue', 0)
    unpaid_count  = status_counts.get('unpaid', 0)

    recent_payments = (
        Payment.objects
        .filter(invoice__student__school=school)
        .select_related('invoice__student')
        .order_by('-paid_at')[:5]
    )

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

    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    method_rows = (
        Payment.objects
        .filter(invoice__student__school=school, paid_at__gte=month_start)
        .values('method')
        .annotate(total=Sum('amount_kes'))
        .order_by('-total')
    )
    method_labels = dict(Payment.Method.choices)
    method_total = sum(float(r['total'] or 0) for r in method_rows)
    method_breakdown = [
        {
            'code': r['method'],
            'label': method_labels.get(r['method'], r['method']),
            'total': float(r['total'] or 0),
            'pct': round((float(r['total'] or 0) / method_total) * 100, 1) if method_total else 0,
        }
        for r in method_rows
    ]

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

    from django.core.paginator import Paginator

    school = request.user.school
    base_qs = Invoice.objects.filter(
        student__school=school
    ).select_related('student', 'fee_structure')

    stats_agg = base_qs.aggregate(
        total=Count('id'),
        paid=Count('id', filter=Q(status='paid')),
        partial=Count('id', filter=Q(status='partial')),
        unpaid=Count('id', filter=Q(status='unpaid')),
        overdue=Count('id', filter=Q(status='overdue')),
    )

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

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

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


# ============================================================
# TRANSACTIONS
# ============================================================

@login_required
def accountant_transactions(request):
    """School accountant sees all transactions, expenditure, debts, credit."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    school = request.user.school
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

    outstanding_agg = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))
    total_debts = float(outstanding_agg['t'] or 0)
    debt_count = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).values('student_id').distinct().count()

    net_position = total_collected - total_expenditure

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

    def delta(curr, prev):
        curr, prev = float(curr or 0), float(prev or 0)
        if prev == 0:
            pct = 100 if curr > 0 else 0
            return {'pct': pct, 'abs': curr - prev, 'direction': 'up' if curr > prev else ('down' if curr < prev else 'flat')}
        pct = round(((curr - prev) / prev) * 100, 1)
        return {'pct': pct, 'abs': curr - prev, 'direction': 'up' if pct > 0 else ('down' if pct < 0 else 'flat')}

    collected_delta = delta(total_collected, prev_collected)
    expenditure_delta = delta(total_expenditure, prev_expenditure)
    net_delta = delta(net_position, prev_collected - prev_expenditure)

    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_student_ids = list(
            Student.objects.filter(school=school, class_level=cls.name, is_active=True).values_list('id', flat=True)
        )
        if not class_student_ids: continue

        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_student_ids,
                paid_at__date__gte=start_date, paid_at__date__lte=end_date,
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
    recent_payments = payments.select_related('invoice__student').order_by('-paid_at')[:20]

    return render(request, 'dashboard/accountant_transactions.html', {
        'period': period, 'period_label': period_label,
        'start_date': start_date, 'end_date': end_date,
        'start_date_iso': start_date.isoformat(), 'end_date_iso': end_date.isoformat(),
        'total_collected': total_collected, 'total_expenditure': total_expenditure,
        'total_debts': total_debts, 'debt_count': debt_count, 'net_position': net_position,
        'method_breakdown': method_breakdown, 'category_breakdown': category_breakdown,
        'class_breakdown': class_breakdown,
        'prev_collected': prev_collected, 'prev_expenditure': prev_expenditure,
        'prev_start': prev_start, 'prev_end': prev_end,
        'collected_delta': collected_delta, 'expenditure_delta': expenditure_delta, 'net_delta': net_delta,
        'recent_payments': recent_payments,
    })


# ============================================================
# STUDENTS & FEES (Accountant)
# ============================================================

@login_required
def accountant_students(request):
    """List all students with their fee balances for the accountant."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    school = request.user.school
    search = request.GET.get('q', '').strip()
    class_id = request.GET.get('class', '')
    status_filter = request.GET.get('status', '').strip()

    students_qs = Student.objects.filter(school=school, is_active=True).order_by('class_level', 'first_name', 'last_name')

    if search:
        students_qs = students_qs.filter(
            Q(first_name__icontains=search) | Q(middle_name__icontains=search) |
            Q(last_name__icontains=search) | Q(admission_number__icontains=search) | Q(upi__icontains=search)
        )
    if class_id:
        cls = ClassLevel.objects.filter(id=class_id, school=school).first()
        if cls:
            students_qs = students_qs.filter(class_level__iexact=cls.name)

    student_ids = list(students_qs.values_list('id', flat=True))
    invoice_totals = (
        Invoice.objects.filter(student_id__in=student_ids).values('student_id')
        .annotate(inv=Sum('amount_due'), pd=Sum('amount_paid'))
    )
    invoice_map = {row['student_id']: {'invoiced': float(row['inv'] or 0), 'paid': float(row['pd'] or 0)} for row in invoice_totals}

    student_list = []
    grand_invoiced = 0
    grand_paid = 0

    for s in students_qs:
        totals = invoice_map.get(s.id, {'invoiced': 0, 'paid': 0})
        total_invoiced = totals['invoiced']
        total_paid = totals['paid']
        balance = total_invoiced - total_paid

        if total_invoiced == 0: status = 'none'
        elif balance <= 0: status = 'paid'
        elif total_paid > 0: status = 'partial'
        else: status = 'unpaid'

        if status_filter and status != status_filter:
            continue

        student_list.append({
            'student': s, 'invoiced': total_invoiced, 'paid': total_paid,
            'balance': balance, 'status': status,
        })
        grand_invoiced += total_invoiced
        grand_paid += total_paid

    return render(request, 'dashboard/accountant_students.html', {
        'students_data': student_list,
        'total_students': len(student_list),
        'grand_invoiced': grand_invoiced,
        'grand_paid': grand_paid,
        'grand_balance': grand_invoiced - grand_paid,
        'classes': ClassLevel.objects.filter(school=school).order_by('order', 'name'),
        'search': search, 'class_id': class_id, 'status_filter': status_filter,
    })


# ============================================================
# GENERATE INVOICES
# ============================================================

@login_required
def generate_invoices(request):
    """Generate invoices in 3 modes: single, class, bulk."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from django.db import transaction
    from apps.finance.models import FeeStructure, Invoice
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from collections import defaultdict

    school = request.user.school

    # ---- Build unique terms list from the dedicated 'term' field ----
    # Example: ['Term 1', 'Term 2', 'Term 3']
    terms_set = set(
        FeeStructure.objects.filter(school=school)
        .values_list('term', flat=True)
        .exclude(term__isnull=True)
        .exclude(term='')
    )
    term_choices = sorted(list(terms_set))
    
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # ---- Helper: find fee structures for a class + exact term ----
    def get_fee_structures(class_name, term):
        return FeeStructure.objects.filter(
            school=school, 
            class_level__name__iexact=class_name, 
            term__iexact=term   # <-- Uses the dedicated 'term' field, not name
        )

    if request.method == 'POST':
        mode = request.POST.get('mode', 'bulk')
        term_name = request.POST.get('term', '').strip()
        custom_term = request.POST.get('custom_term', '').strip()
        term_prefix = custom_term or term_name

        if not term_prefix:
            messages.error(request, 'Please select or type a term.')
            return redirect('generate_invoices')

        # ==========================================================
        # MODE: SINGLE STUDENT
        # ==========================================================
        if mode == 'single':
            student_id = request.POST.get('student_id')
            custom_amount = request.POST.get('custom_amount', '').strip()
            override_amount = request.POST.get('override_amount', '').strip()

            student = Student.objects.filter(id=student_id, school=school, is_active=True).first()
            if not student:
                messages.error(request, 'Student not found.')
                return redirect('generate_invoices')

            term_fs = get_fee_structures(student.class_level, term_prefix)
            
            if not term_fs.exists():
                messages.error(request, f'No fee structure found for {student.class_level} in {term_prefix}.')
                return redirect('generate_invoices')

            if override_amount and custom_amount:
                try:
                    amount = float(custom_amount)
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid custom amount.')
                    return redirect('generate_invoices')
                anchor = term_fs.first()
            else:
                amount = sum(float(f.amount_kes) for f in term_fs)
                anchor = term_fs.first()

            invoice, created = Invoice.objects.get_or_create(
                student=student, fee_structure=anchor,
                defaults={'amount_due': amount, 'due_date': anchor.due_date},
            )
            invoice.amount_due = amount
            invoice.due_date = anchor.due_date
            invoice.save(update_fields=['amount_due', 'due_date'])
            invoice.update_status()

            messages.success(request, f'Invoice {"created" if created else "updated"} for {student.full_name}. Total: KES {amount:,.2f}')
            return redirect('accountant_invoices')

        # ==========================================================
        # MODE: SINGLE CLASS
        # ==========================================================
        if mode == 'class':
            class_name = request.POST.get('class_name', '').strip()
            term_fs = get_fee_structures(class_name, term_prefix)
            
            if not term_fs.exists():
                messages.error(request, f'No fee structure found for {class_name} in {term_prefix}. Please draft the fees in the Matrix first.')
                return redirect('generate_invoices')

            amount = sum(float(f.amount_kes) for f in term_fs)
            anchor = term_fs.first()
            due_date = anchor.due_date

            students = Student.objects.filter(school=school, class_level__iexact=class_name, is_active=True)
            created_count = 0

            with transaction.atomic():
                for s in students:
                    inv, was_created = Invoice.objects.get_or_create(
                        student=s, fee_structure=anchor,
                        defaults={'amount_due': amount, 'due_date': due_date},
                    )
                    if was_created:
                        created_count += 1
                        inv.update_status()

            messages.success(request, f'{class_name}: {created_count} new invoices created at KES {amount:,.2f} each.')
            return redirect('accountant_invoices')

        # ==========================================================
        # MODE: BULK (ALL CLASSES)
        # ==========================================================
        if mode == 'bulk':
            matching_fs = FeeStructure.objects.filter(
                school=school, term__iexact=term_prefix
            )

            if not matching_fs.exists():
                messages.error(request, f'No fee structures found for {term_prefix}.')
                return redirect('generate_invoices')

            by_class = defaultdict(list)
            for fs in matching_fs:
                by_class[fs.class_level.name].append(fs)

            created_count = 0
            classes_processed = 0
            total_billed = 0

            with transaction.atomic():
                for class_name, fee_list in by_class.items():
                    total_fee = sum(float(f.amount_kes) for f in fee_list)
                    if total_fee <= 0: continue
                    anchor_fs = fee_list[0]
                    due_date = anchor_fs.due_date
                    
                    students = Student.objects.filter(school=school, class_level__iexact=class_name, is_active=True)
                    
                    for student in students:
                        inv, was_created = Invoice.objects.get_or_create(
                            student=student, fee_structure=anchor_fs,
                            defaults={'amount_due': total_fee, 'due_date': due_date},
                        )
                        if was_created:
                            created_count += 1
                            total_billed += total_fee
                            inv.update_status()
                    classes_processed += 1

            messages.success(request, f'Bulk ({term_prefix}): {created_count} invoices created across {classes_processed} classes. Total billed: KES {total_billed:,.2f}')
            return redirect('accountant_invoices')

    # ==========================================================
    # GET — render form + preview
    # ==========================================================
    preview_term = request.GET.get('term', '').strip()
    preview = None
    
    if preview_term:
        matching = FeeStructure.objects.filter(school=school, term__iexact=preview_term)
        by_class = defaultdict(lambda: {'total': 0.0, 'due_date': None})
        for fs in matching:
            by_class[fs.class_level.name]['total'] += float(fs.amount_kes)
            if not by_class[fs.class_level.name]['due_date']:
                by_class[fs.class_level.name]['due_date'] = fs.due_date

        preview_classes = []
        grand_total = 0
        total_students = 0
        for class_name, data in by_class.items():
            count = Student.objects.filter(school=school, class_level__iexact=class_name, is_active=True).count()
            if count == 0: continue
            class_total = data['total'] * count
            grand_total += class_total
            total_students += count
            preview_classes.append({
                'class_name': class_name, 'per_student': data['total'],
                'student_count': count, 'class_total': class_total, 'due_date': data['due_date'],
            })
        preview_classes.sort(key=lambda x: x['class_name'])
        preview = {
            'term': preview_term, 'classes': preview_classes,
            'total_students': total_students, 'grand_total': grand_total,
        }

    all_students = Student.objects.filter(school=school, is_active=True).order_by('class_level', 'first_name', 'last_name')

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

    school = request.user.school
    student = get_object_or_404(Student, id=student_id, school=school)

    fs_qs = FeeStructure.objects.filter(
        school=school, class_level__name__iexact=student.class_level
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

        term_fs = fs_qs.filter(name__startswith=f"{term_name} —")
        if not term_fs.exists():
            messages.error(request, f'No fees for "{term_name}".')
            return redirect('invoice_student_quick', student_id=student.id)
        anchor = term_fs.first()

        if override and custom_amount:
            try:
                amount = float(custom_amount)
                if amount <= 0: raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'Invalid custom amount.')
                return redirect('invoice_student_quick', student_id=student.id)
        else:
            amount = sum(float(f.amount_kes) for f in term_fs)

        invoice, created = Invoice.objects.get_or_create(
            student=student, fee_structure=anchor,
            defaults={'amount_due': amount, 'due_date': anchor.due_date},
        )
        invoice.amount_due = amount
        invoice.due_date = anchor.due_date
        invoice.save(update_fields=['amount_due', 'due_date'])
        invoice.update_status()

        messages.success(request, f'Invoice {"created" if created else "updated"} for {student.full_name}.')
        return redirect('accountant_students')

    return render(request, 'dashboard/invoice_student_quick.html', {
        'student': student, 'term_options': term_options,
    })


# ============================================================
# PAYMENTS
# ============================================================

@login_required
def record_payment(request, invoice_id):
    """Record a manual payment against an invoice."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    invoice = get_object_or_404(Invoice, id=invoice_id, student__school=request.user.school)

    if request.method == 'POST':
        amount = request.POST.get('amount', '').strip()
        method = request.POST.get('method', 'cash')
        external_ref = request.POST.get('external_reference', '').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Please enter a valid amount.')
            amount = 0

        if method not in [c[0] for c in Payment.Method.choices]:
            errors.append('Invalid payment method.')
        if method in ('mpesa', 'airtel', 'bank', 'cheque') and not external_ref:
            errors.append(f'Please enter the {method.upper()} transaction reference.')

        if errors:
            for e in errors: messages.error(request, e)
            return redirect('record_payment', invoice_id=invoice.id)

        try:
            payment = Payment.objects.create(
                invoice=invoice, amount_kes=amount, method=method,
                external_reference=external_ref, notes=notes, recorded_by=request.user,
            )
            messages.success(request, f'Payment recorded. Reference: {payment.reference}')
            return redirect('accountant_invoices')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'dashboard/record_payment.html', {
        'invoice': invoice, 'methods': Payment.Method.choices,
    })


# ============================================================
# FINANCIAL REPORT
# ============================================================

@login_required
def financial_report_pdf(request):
    """Generate a financial report PDF for the selected period."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school
    today = date.today()

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

    payments = Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=start_date, paid_at__date__lte=end_date,
    ).select_related('invoice__student')
    total_collected = float(payments.aggregate(t=Sum('amount_kes'))['t'] or 0)
    method_breakdown = {
        dict(Payment.Method.choices).get(r['method'], r['method']): float(r['t'] or 0)
        for r in payments.values('method').annotate(t=Sum('amount_kes'))
    }

    expenditures = Expenditure.objects.filter(
        school=school, spent_on__gte=start_date, spent_on__lte=end_date,
    )
    total_expenditure = float(expenditures.aggregate(t=Sum('amount_kes'))['t'] or 0)
    category_breakdown = {
        dict(Expenditure.Category.choices).get(r['category'], r['category']): float(r['t'] or 0)
        for r in expenditures.values('category').annotate(t=Sum('amount_kes'))
    }

    net_position = total_collected - total_expenditure
    outstanding_agg = Invoice.objects.filter(
        student__school=school, status__in=['unpaid', 'partial', 'overdue'],
    ).aggregate(t=Sum(F('amount_due') - F('amount_paid')))
    total_outstanding = float(outstanding_agg['t'] or 0)

    class_breakdown = []
    for cls in ClassLevel.objects.filter(school=school).order_by('order', 'name'):
        class_students = list(Student.objects.filter(school=school, class_level=cls.name, is_active=True).values_list('id', flat=True))
        if not class_students: continue
        class_collected = float(
            Payment.objects.filter(
                invoice__student_id__in=class_students,
                paid_at__date__gte=start_date, paid_at__date__lte=end_date,
            ).aggregate(t=Sum('amount_kes'))['t'] or 0
        )
        class_breakdown.append({'class_name': cls.name, 'students': len(class_students), 'collected': class_collected})
    class_breakdown.sort(key=lambda x: x['collected'], reverse=True)

    period_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_days - 1)

    prev_collected = float(Payment.objects.filter(
        invoice__student__school=school,
        paid_at__date__gte=prev_start, paid_at__date__lte=prev_end,
    ).aggregate(t=Sum('amount_kes'))['t'] or 0)
    prev_expenditure = float(Expenditure.objects.filter(
        school=school, spent_on__gte=prev_start, spent_on__lte=prev_end,
    ).aggregate(t=Sum('amount_kes'))['t'] or 0)

    html_string = render_to_string('pdf/financial_report.html',
        build_pdf_context(
            school=school, generated_by=request.user,
            period_label=period_label, start_date=start_date, end_date=end_date,
            prev_start=prev_start, prev_end=prev_end,
            total_collected=total_collected, total_expenditure=total_expenditure,
            total_outstanding=total_outstanding, net_position=net_position,
            prev_collected=prev_collected, prev_expenditure=prev_expenditure,
            method_breakdown=method_breakdown, category_breakdown=category_breakdown,
            class_breakdown=class_breakdown,
        )
    )
    return html_to_pdf_response(html_string, f'financial_report_{start_date.isoformat()}_{end_date.isoformat()}.pdf')


# ============================================================
# CLASS FEE STATEMENT
# ============================================================

@login_required
@role_required('accountant', 'principal')
def class_fee_statement(request):
    """Shows fee summary for one class + per-student breakdown."""
    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    class_id = request.GET.get('class')
    if not class_id and classes.exists():
        class_id = classes.first().id

    selected_class = None
    if class_id:
        selected_class = ClassLevel.objects.filter(id=class_id, school=school).first()

    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    students_data = []
    class_invoiced = 0
    class_paid = 0
    counts = {'paid': 0, 'partial': 0, 'unpaid': 0, 'overdue': 0, 'none': 0}

    if selected_class:
        students_qs = Student.objects.filter(
            school=school, class_level__iexact=selected_class.name, is_active=True,
        ).order_by('first_name', 'last_name')

        if search:
            students_qs = students_qs.filter(
                Q(first_name__icontains=search) | Q(middle_name__icontains=search) |
                Q(last_name__icontains=search) | Q(admission_number__icontains=search)
            )

        for s in students_qs:
            invoices = Invoice.objects.filter(student=s)
            total_invoiced = sum(i.amount_due for i in invoices) or 0
            total_paid = sum(i.amount_paid for i in invoices) or 0
            balance = total_invoiced - total_paid

            if total_invoiced == 0: status = 'none'
            elif balance <= 0: status = 'paid'
            elif any(i.status == 'overdue' for i in invoices): status = 'overdue'
            elif total_paid > 0: status = 'partial'
            else: status = 'unpaid'

            counts[status] = counts.get(status, 0) + 1
            if status_filter and status != status_filter: continue

            students_data.append({
                'student': s, 'invoiced': total_invoiced, 'paid': total_paid,
                'balance': balance, 'status': status, 'invoice_count': invoices.count(),
            })
            class_invoiced += total_invoiced
            class_paid += total_paid

    return render(request, 'dashboard/class_fee_statement.html', {
        'classes': classes, 'selected_class': selected_class,
        'students_data': students_data, 'total_students': len(students_data),
        'class_invoiced': class_invoiced, 'class_paid': class_paid,
        'class_balance': class_invoiced - class_paid, 'counts': counts,
        'search': search, 'status_filter': status_filter,
    })


@login_required
@role_required('accountant', 'principal')
def class_fee_statement_pdf(request, class_id):
    """Generate PDF of class fee statement."""
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school
    selected_class = ClassLevel.objects.filter(id=class_id, school=school).first()
    if not selected_class:
        messages.error(request, 'Class not found.')
        return redirect('class_fee_statement')

    students = Student.objects.filter(school=school, class_level__iexact=selected_class.name, is_active=True).order_by('first_name', 'last_name')

    students_data = []
    class_invoiced = 0
    class_paid = 0
    for s in students:
        invoices = Invoice.objects.filter(student=s)
        total_invoiced = sum(i.amount_due for i in invoices) or 0
        total_paid = sum(i.amount_paid for i in invoices) or 0
        balance = total_invoiced - total_paid
        status = 'none' if total_invoiced == 0 else ('paid' if balance <= 0 else ('partial' if total_paid > 0 else 'unpaid'))
        students_data.append({'student': s, 'invoiced': total_invoiced, 'paid': total_paid, 'balance': balance, 'status': status})
        class_invoiced += total_invoiced
        class_paid += total_paid

    html_string = render_to_string('pdf/class_fee_statement.html',
        build_pdf_context(
            school=school, generated_by=request.user, selected_class=selected_class,
            students_data=students_data, total_students=len(students_data),
            class_invoiced=class_invoiced, class_paid=class_paid,
            class_balance=class_invoiced - class_paid, printed_by=request.user,
        )
    )
    return html_to_pdf_response(html_string, f'class_statement_{selected_class.name.replace(" ", "_")}.pdf')


# ============================================================
# FEE STRUCTURE CRUD
# ============================================================

@login_required
def fee_structure_list(request):
    """View and manage fee structures with search and filtering."""
    if request.user.role not in ('accountant', 'principal', 'bursar', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    
    # 1. Get filter parameters from the URL
    search_query = request.GET.get('q', '').strip()
    selected_class_id = request.GET.get('class_id', '').strip()
    selected_term = request.GET.get('term', '').strip()
    
    # 2. Base queryset
    fees = FeeStructure.objects.filter(school=school).select_related('class_level').order_by('class_level__order', 'created_at')
    
    # 3. Apply Filters
    if search_query:
        fees = fees.filter(name__icontains=search_query)
        
    if selected_class_id:
        fees = fees.filter(class_level_id=selected_class_id)
        
    if selected_term:
        fees = fees.filter(term=selected_term)

    # 4. Group the fees by Class and Term for the UI
    groups_dict = {}
    for fee in fees:
        # Unique key combining class, term, and year
        key = f"{fee.class_level.id}_{fee.term}_{fee.academic_year}"
        
        if key not in groups_dict:
            groups_dict[key] = {
                'class_name': fee.class_level.name,
                'class_id': fee.class_level.id,
                'term': fee.term,
                'academic_year': fee.academic_year,
                'items': [],
                'total': 0,
            }
            
        groups_dict[key]['items'].append(fee)
        groups_dict[key]['total'] += fee.amount_kes

    # Convert dictionary to list for the template
    grouped_fees = list(groups_dict.values())

    # 5. Determine if any filters were applied
    has_filters = bool(search_query or selected_class_id or selected_term)

    return render(request, 'dashboard/fee_structure_list.html', {
        'classes': classes,
        'grouped_fees': grouped_fees,
        'search_query': search_query,
        'selected_class_id': int(selected_class_id) if selected_class_id else None,
        'selected_term': selected_term,
        'has_filters': has_filters,
    })

@login_required
@role_required('accountant', 'principal')
def fee_structure_add(request):
    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        class_val = request.POST.get('class_level', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None

        errors = []
        if not name: errors.append('Name is required.')
        if not class_val: errors.append('Class is required.')
        try:
            amount = float(amount)
            if amount <= 0: errors.append('Amount must be greater than zero.')
        except (ValueError, TypeError):
            errors.append('Invalid amount.')
        if not due_date: errors.append('Due date is required.')

        if errors:
            for e in errors: messages.error(request, e)
            return render(request, 'dashboard/fee_structure_form.html', {
                'classes': classes, 'action': 'add', 'form_data': request.POST,
            })

        if class_val.isdigit():
            cls = ClassLevel.objects.filter(id=class_val, school=school).first()
        else:
            cls = ClassLevel.objects.filter(name__iexact=class_val, school=school).first()

        if not cls:
            messages.error(request, 'Invalid class.')
            return redirect('fee_structure_add')

        FeeStructure.objects.create(
            school=school, name=name, class_level=cls,
            amount_kes=amount, due_date=due_date,
        )
        messages.success(request, f'Fee structure "{name}" created for {cls.name}.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {'classes': classes, 'action': 'add'})


@login_required
@role_required('accountant', 'principal')
def fee_structure_edit(request, fee_id):
    school = request.user.school
    fs = get_object_or_404(FeeStructure, id=fee_id, school=school)
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        fs.name = request.POST.get('name', fs.name).strip()

        class_val = request.POST.get('class_level')
        if class_val:
            if class_val.isdigit():
                cls = ClassLevel.objects.filter(id=class_val, school=school).first()
            else:
                cls = ClassLevel.objects.filter(name__iexact=class_val, school=school).first()
            if cls:
                fs.class_level = cls
            else:
                messages.error(request, 'Invalid class selected.')
                return redirect('fee_structure_edit', fee_id=fs.id)

        fs.due_date = request.POST.get('due_date') or fs.due_date
        try:
            fs.amount_kes = float(request.POST.get('amount_kes', fs.amount_kes))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount.')
            return redirect('fee_structure_edit', fee_id=fs.id)

        fs.save()
        messages.success(request, f'Fee structure "{fs.name}" updated.')
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_form.html', {
        'classes': classes, 'fee_structure': fs, 'action': 'edit',
    })


@login_required
@role_required('accountant', 'principal')
def fee_structure_delete(request, fee_id):
    fs = get_object_or_404(FeeStructure, id=fee_id, school=request.user.school)
    name = fs.name
    fs.delete()
    messages.success(request, f'Fee structure "{name}" deleted.')
    return redirect('fee_structure_list')


@login_required
@role_required('accountant', 'principal')
def fee_structure_bulk(request):
    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        due_date = request.POST.get('due_date') or None
        selected_class_ids = request.POST.getlist('classes')
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
                'classes': classes, 'form_data': request.POST,
            })

        created = 0
        skipped = 0
        for class_id in selected_class_ids:
            cls = ClassLevel.objects.filter(id=class_id, school=school).first()
            if not cls: continue

            exists = FeeStructure.objects.filter(school=school, name=name, class_level=cls).exists()
            if exists and skip_existing:
                skipped += 1
                continue

            FeeStructure.objects.create(
                school=school, name=name, class_level=cls,
                amount_kes=amount, due_date=due_date,
            )
            created += 1

        messages.success(request, f'Created {created} fee structures.' + (f' Skipped {skipped} duplicates.' if skipped else ''))
        return redirect('fee_structure_list')

    return render(request, 'dashboard/fee_structure_bulk.html', {'classes': classes})


# ============================================================
# FEE STRUCTURE MATRIX (SINGLE SOURCE OF TRUTH)
# ============================================================

@login_required
def fee_structure_matrix(request):
    """Bulk draft page — matrix editor for fee items × classes."""
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

    from datetime import date
    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    
    # 1. Fetch existing years from the database, or default to the current year
    current_year = date.today().year
    existing_years = FeeStructure.objects.filter(school=school).values_list('academic_year', flat=True).distinct()
    
    # Convert everything to strings to avoid int vs str comparison errors
    years_set = set(str(y) for y in existing_years if y)
    years_set.add(str(current_year))
    years_set.add(str(current_year + 1))
    years = sorted(list(years_set))

    # 2. Build term options
    terms = ['Term 1', 'Term 2', 'Term 3']

    # 3. Default values
    today = timezone.now().date()
    default_term_name = f"Term {((today.month - 1) // 4) + 1}"
    default_year = str(today.year)
    default_due_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')

    return render(request, 'dashboard/fee_structure_matrix.html', {
        'classes': classes,
        'years': years,
        'terms': terms,
        'default_term_name': default_term_name,
        'default_year': default_year,
        'default_due_date': default_due_date,
    })


@login_required
def fee_structure_matrix_save(request):
    """Receives the bulk JSON and creates FeeStructure rows for selected classes and multiple fee items."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    if request.user.role not in ('accountant', 'principal'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)

    import json
    from django.db import transaction

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    term_name = (payload.get('term') or '').strip()
    year = (payload.get('year') or '').strip()
    class_ids = payload.get('class_ids') or []
    fee_items = payload.get('fee_items') or []

    if not term_name or not year or not class_ids or not fee_items:
        return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)

    school = request.user.school
    valid_class_ids = set(ClassLevel.objects.filter(school=school).values_list('id', flat=True))

    created = 0
    try:
        with transaction.atomic():
            for class_id in class_ids:
                cid = int(class_id)
                if cid not in valid_class_ids:
                    continue

                for item in fee_items:
                    item_name = item.get('name', '').strip()
                    amount = item.get('amount')
                    due_date_str = item.get('due_date', '').strip()
                    
                    if not item_name or amount is None or not due_date_str:
                        continue
                        
                    try:
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        continue

                    # Check if this fee already exists for this class/term to avoid duplicates
                    exists = FeeStructure.objects.filter(
                        school=school, 
                        class_level_id=cid, 
                        term=term_name, 
                        academic_year=year, 
                        name=item_name
                    ).exists()

                    if not exists:
                        FeeStructure.objects.create(
                            school=school,
                            class_level_id=cid,
                            name=item_name,
                            amount_kes=amount,
                            due_date=due_date,
                            academic_year=year,
                            term=term_name
                        )
                        created += 1
                    
        return JsonResponse({'success': True, 'message': f'Successfully created {created} fee records across the selected classes.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@login_required
def fee_structure_class_pdf(request, class_name):
    """Generate a PDF of all fee items for a specific class."""
    from django.template.loader import render_to_string
    from apps.core.pdf_utils import html_to_pdf_response

    school = request.user.school
    fees = FeeStructure.objects.filter(school=school, class_level__name=class_name)
    total = sum(fee.amount_kes for fee in fees)
    context = build_pdf_context(school=school, generated_by=request.user, class_name=class_name, fees=fees, total=total)
    html_string = render_to_string('pdf/fee_structure.html', context)
    return html_to_pdf_response(html_string, f'Fee_Structure_{class_name}.pdf')


# ============================================================
# EXPENDITURES
# ============================================================

@login_required
def expenditure_list(request):
    from django.core.paginator import Paginator
    from django.utils.dateparse import parse_date

    school = request.user.school
    base_qs = Expenditure.objects.filter(school=school).select_related('recorded_by').order_by('-spent_on', '-created_at')

    category = request.GET.get('category', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    search = request.GET.get('q', '').strip()

    qs = base_qs
    if category: qs = qs.filter(category=category)
    if date_from:
        d = parse_date(date_from)
        if d: qs = qs.filter(spent_on__gte=d)
    if date_to:
        d = parse_date(date_to)
        if d: qs = qs.filter(spent_on__lte=d)
    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(paid_to__icontains=search) | Q(reference__icontains=search))

    agg = qs.aggregate(total=Sum('amount_kes'), count=Count('id'))
    category_labels = dict(Expenditure.Category.choices)
    category_summary = [
        {'code': row['category'], 'label': category_labels.get(row['category'], row['category']), 'total': float(row['subtotal'] or 0), 'count': row['cnt']}
        for row in qs.values('category').annotate(subtotal=Sum('amount_kes'), cnt=Count('id')).order_by('-subtotal')
    ]

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/expenditure_list.html', {
        'expenditures': page_obj, 'page_obj': page_obj, 'paginator': paginator,
        'total': float(agg['total'] or 0), 'count': agg['count'] or 0,
        'categories': Expenditure.Category.choices, 'category_summary': category_summary,
        'category_filter': category, 'date_from': date_from, 'date_to': date_to, 'search': search,
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_add(request):
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
                school=request.user.school, category=category, description=description,
                amount_kes=amount, spent_on=spent_on, paid_to=paid_to,
                payment_method=payment_method, reference=reference, notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'Expenditure of KES {amount:,.2f} recorded.')
            return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices, 'action': 'add',
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_edit(request, expenditure_id):
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
        messages.success(request, 'Expenditure updated.')
        return redirect('expenditure_list')

    return render(request, 'dashboard/expenditure_form.html', {
        'categories': Expenditure.Category.choices, 'expenditure': exp, 'action': 'edit',
    })


@login_required
@role_required('accountant', 'principal')
def expenditure_delete(request, expenditure_id):
    exp = get_object_or_404(Expenditure, id=expenditure_id, school=request.user.school)
    if request.method == 'POST':
        desc = exp.description
        exp.delete()
        messages.success(request, f'Expenditure "{desc}" deleted.')
        return redirect('expenditure_list')
    return render(request, 'dashboard/expenditure_delete.html', {'expenditure': exp})


@login_required
@role_required('accountant', 'principal')
def expenditure_pdf(request):
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    school = request.user.school
    qs = Expenditure.objects.filter(school=school).order_by('-spent_on')

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
    category_totals = {}
    for e in qs:
        cat = e.get_category_display()
        category_totals[cat] = category_totals.get(cat, 0) + float(e.amount_kes)

    html_string = render_to_string('pdf/expenditure_statement.html',
        build_pdf_context(
            school=school, generated_by=request.user, expenditures=qs,
            total=total, count=qs.count(), category_totals=category_totals,
            category_filter=category, date_from=date_from, date_to=date_to,
            printed_by=request.user,
        )
    )
    return html_to_pdf_response(html_string, 'expenditure_statement.pdf')


@login_required
def add_expenditure(request):
    if request.user.role not in ('accountant', 'principal'):
        return redirect('dashboard_home')

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
                school=request.user.school, category=category, description=description,
                amount_kes=amount, spent_on=spent_on, paid_to=paid_to,
                payment_method=payment_method, reference=reference, notes=notes,
                recorded_by=request.user,
            )
            messages.success(request, f'Expenditure of KES {amount:,.2f} recorded.')
            return redirect('accountant_transactions')

    return render(request, 'dashboard/add_expenditure.html', {
        'categories': Expenditure.Category.choices,
    })


# ============================================================
# PARENT M-PESA PAYMENT
# ============================================================

@login_required
def parent_mpesa_payment(request):
    """Allows a parent to trigger an STK push for fees or wallet."""
    if request.user.role not in ('parent', 'super_admin'):
        return redirect('dashboard_home')

    from apps.parents.models import Parent
    from apps.finance.services.mpesa import stk_push

    parent_profile = get_object_or_404(Parent, user=request.user)
    children = parent_profile.students.all()

    if not children.exists():
        messages.warning(request, "No students are linked to your account. Please contact the school.")
        return redirect('dashboard_home')

    preselected_child_id = request.GET.get('child_id')
    selected_child = children.first()
    if preselected_child_id and str(preselected_child_id).isdigit():
        selected_child = children.filter(id=preselected_child_id).first() or selected_child

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if not student_id or not str(student_id).isdigit():
            messages.error(request, "Invalid student selected.")
            return redirect('parent_mpesa_payment')

        amount = request.POST.get('amount')
        phone = request.POST.get('phone')
        purpose = request.POST.get('purpose')

        student = get_object_or_404(Student, id=student_id, parents=parent_profile)

        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]

        school = request.user.school

        if not hasattr(school, 'mpesa_config') or not school.mpesa_config.paybill_number:
            messages.error(request, "School M-Pesa Paybill is not configured. Please contact the accountant.")
            return redirect('parent_mpesa_payment')

        account_ref = student.admission_number
        if purpose == 'wallet':
            account_ref += '-WAL'

        if not school.mpesa_config.consumer_key or not school.mpesa_config.consumer_secret:
            messages.error(request, "The school has not configured their M-Pesa Daraja API keys yet.")
            return redirect('parent_mpesa_payment')

        try:
            response = stk_push(
                phone=phone, amount=Decimal(amount), account_ref=account_ref,
                description=f"{purpose.title()} Payment - {student.first_name}",
                shortcode=school.mpesa_config.paybill_number,
                passkey=school.mpesa_config.passkey,
                consumer_key=school.mpesa_config.consumer_key,
                consumer_secret=school.mpesa_config.consumer_secret,
                callback_url=school.mpesa_config.callback_url,
            )
            if response and response.get('CheckoutRequestID'):
                messages.success(request, f"STK Push sent for {student.first_name}. Please enter your M-Pesa PIN.")
            else:
                messages.error(request, f"Failed to initiate: {response}")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect(f"/dashboard/parent/pay/?child_id={student.id}")

    return render(request, 'dashboard/parent_mpesa_payment.html', {
        'children': children, 'selected_child': selected_child, 'school': request.user.school,
    })

@login_required
def download_fee_structure_pdf(request, class_id):
    """Generates a premium PDF for a specific class fee structure."""
    if request.user.role not in ('accountant', 'principal', 'bursar', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    class_level = get_object_or_404(ClassLevel, id=class_id, school=school)
    
    # Get the term and year from the URL (e.g., ?term=Term+1&year=2024)
    term = request.GET.get('term', 'Term 1')
    year = request.GET.get('year', '2024')

    # Fetch all fees for this specific class
    fees = FeeStructure.objects.filter(
        school=school, 
        class_level=class_level,
        term=term,
        academic_year=year
    ).order_by('created_at')

    # Calculate total
    total_amount = sum(fee.amount_kes for fee in fees)

    # Get school logo
    school_logo_b64 = get_school_logo_data_uri(school, max_width=120)

    # Render HTML
    html_string = render_to_string('pdf/fee_structure_pdf.html', {
        'school': school,
        'class_level': class_level,
        'term': term,
        'academic_year': year,
        'fees': fees,
        'total_amount': total_amount,
        'generated_by': request.user,
        'school_logo_b64': school_logo_b64,
    })

    # Generate and return PDF
    filename = f'fee_structure_{class_level.name.replace(" ", "_")}_{term}_{year}.pdf'
    return html_to_pdf_response(html_string, filename)