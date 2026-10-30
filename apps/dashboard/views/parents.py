"""
Parent views:
- Parent list (admin view)
- Parent dashboard
- Parent's children (list + detail)
- Add/delete/link parent (admin)
- Child fee statement PDF (parent)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum, Avg

from apps.accounts.decorators import (
    role_required, school_staff_only, parent_only,
)
from apps.core.pdf_utils import build_pdf_context


@login_required
def parents_list(request):
    """List all parents with filters, stats, and pagination."""
    if request.user.role != 'principal':
        return redirect('dashboard_home')

    from apps.parents.models import Parent
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    school = request.user.school

    base_qs = Parent.objects.filter(
        user__school=school
    ).select_related('user').prefetch_related('students')

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    rel_filter = request.GET.get('relationship', '').strip()
    link_filter = request.GET.get('linked', '').strip()

    qs = base_qs.order_by('user__first_name', 'user__last_name')

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(phone__icontains=search) |
            Q(id_number__icontains=search) |
            Q(students__first_name__icontains=search) |
            Q(students__last_name__icontains=search)
        ).distinct()

    if rel_filter:
        qs = qs.filter(relationship=rel_filter)

    if link_filter == 'linked':
        qs = qs.filter(students__isnull=False).distinct()
    elif link_filter == 'unlinked':
        qs = qs.filter(students__isnull=True)

    # ---------- Stats ----------
    total_parents = base_qs.count()
    linked_parents = base_qs.filter(students__isnull=False).distinct().count()
    total_children = 0
    boys_count = 0
    girls_count = 0
    for p in base_qs.prefetch_related('students'):
        for s in p.students.all():
            total_children += 1
            if s.gender == 'M':
                boys_count += 1
            else:
                girls_count += 1

    stats = {
        'total': total_parents,
        'linked': linked_parents,
        'unlinked': total_parents - linked_parents,
        'children': total_children,
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/parents_list.html', {
        'parents': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'rel_filter': rel_filter,
        'link_filter': link_filter,
        'relationships': Parent.Relationship.choices,
        'total_filtered': qs.count(),
    })


@login_required
def parent_dash(request):
    """Parent dashboard — children, invoices, attendance summary."""
    children = []
    invoices = []
    total_due = 0
    total_invoiced = 0
    total_paid = 0
    stats = {
        'children_count': 0,
        'invoices_count': 0,
        'unpaid_count': 0,
    }

    try:
        children = request.user.parent_profile.students.all()

        from apps.finance.models import Invoice
        from django.db.models import Sum

        invoices = Invoice.objects.filter(
            student__in=children
        ).select_related('student', 'fee_structure').order_by('-created_at')

        # Aggregates
        agg = invoices.aggregate(
            due=Sum('amount_due'),
            paid=Sum('amount_paid'),
        )
        total_invoiced = float(agg['due'] or 0)
        total_paid = float(agg['paid'] or 0)
        total_due = total_invoiced - total_paid

        stats = {
            'children_count': children.count(),
            'invoices_count': invoices.count(),
            'unpaid_count': invoices.filter(
                status__in=['unpaid', 'partial', 'overdue']
            ).count(),
        }
    except Exception:
        pass

    return render(request, 'dashboard/parent.html', {
        'children': children,
        'invoices': invoices[:10],  # show latest 10
        'total_due': total_due,
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'stats': stats,
    })


@login_required
@parent_only
def parent_children(request):
    if request.user.role != 'parent':
        return redirect('dashboard_home')

    children = []
    try:
        children = request.user.parent_profile.students.all()
    except Exception:
        pass

    return render(request, 'dashboard/parent_children.html', {'children': children})


@login_required
@parent_only
def parent_child_detail(request, student_id):
    """Detail view for one child: grades, attendance, invoices, fees, statement."""
    from apps.students.models import Student
    from apps.grades.models import Grade
    from apps.attendance.models import Attendance
    from apps.finance.models import Invoice, Payment, FeeStructure
    from django.utils import timezone
    from datetime import date, timedelta

    # Security — parent can only see their own children
    try:
        child = request.user.parent_profile.students.get(id=student_id)
    except Exception:
        messages.error(request, 'Child not found.')
        return redirect('parent_children')

    # ---------- Grades grouped by exam ----------
    grades_qs = Grade.objects.filter(student=child).select_related(
        'subject', 'exam'
    ).order_by('-exam__year', '-exam__id', 'subject__name')

    exams_map = {}
    for g in grades_qs:
        exams_map.setdefault(g.exam, []).append(g)

    exam_summaries = []
    for exam, grade_list in exams_map.items():
        total = sum(g.marks for g in grade_list)
        out_of = sum(g.out_of for g in grade_list) or 1
        avg = round((float(total) / float(out_of)) * 100, 1) if grade_list else 0

        if avg >= 80:
            cbc, cbc_label, cbc_color = 'EE', 'Exceeding Expectation', 'green'
        elif avg >= 65:
            cbc, cbc_label, cbc_color = 'ME', 'Meeting Expectation', 'blue'
        elif avg >= 50:
            cbc, cbc_label, cbc_color = 'AE', 'Approaching Expectation', 'yellow'
        else:
            cbc, cbc_label, cbc_color = 'BE', 'Below Expectation', 'red'

        exam_summaries.append({
            'exam': exam,
            'grades': sorted(grade_list, key=lambda x: x.subject.name),
            'total': total,
            'out_of': out_of,
            'avg': avg,
            'cbc': cbc,
            'cbc_label': cbc_label,
            'cbc_color': cbc_color,
        })

    # ---------- Attendance (last 30 days) ----------
    thirty_days_ago = date.today() - timedelta(days=30)
    att_qs = Attendance.objects.filter(student=child, date__gte=thirty_days_ago)
    present_30 = att_qs.filter(status='P').count()
    absent_30 = att_qs.filter(status='A').count()
    late_30 = att_qs.filter(status='L').count()
    total_marked = present_30 + absent_30 + late_30
    attendance_pct = round((present_30 / total_marked) * 100, 1) if total_marked else 0

    # ---------- Invoices + Total Due ----------
    invoices = Invoice.objects.filter(student=child).select_related('fee_structure')
    total_due = sum(i.balance for i in invoices)

    # ---------- Fee Structure for child's class ----------
    fee_rows = []
    fee_total = 0
    if child.class_level:
        fs_qs = FeeStructure.objects.filter(
            school=child.school,
            class_level=child.class_level,
        ).order_by('name')
        for fs in fs_qs:
            # Extract item name from "Term 1 2026 — Tuition" format
            name = fs.name
            if ' — ' in name:
                term_part, item_part = name.split(' — ', 1)
                display_name = item_part
            else:
                display_name = name

            fee_rows.append({
                'name': display_name,
                'amount': float(fs.amount_kes),
                'due_date': fs.due_date,
            })
            fee_total += float(fs.amount_kes)

    # ---------- Statement (ledger) ----------
    period = request.GET.get('period', 'term')
    now = timezone.now()

    if period == 'term':
        # Current term = last 90 days
        start = now - timedelta(days=90)
    elif period == 'year':
        # Current year
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
    else:  # 'all'
        start = None

    invoice_qs = Invoice.objects.filter(student=child)
    payment_qs = Payment.objects.filter(invoice__student=child).select_related('invoice')

    if start:
        invoice_qs = invoice_qs.filter(created_at__gte=start)
        payment_qs = payment_qs.filter(paid_at__gte=start)

    # Build ledger sorted by date
    ledger_events = []
    for inv in invoice_qs:
        ledger_events.append({
            'date': inv.created_at.date(),
            'description': f"Invoice — {inv.fee_structure.name if inv.fee_structure else 'Fee'}",
            'charge': float(inv.amount_due),
            'payment': None,
        })
    for p in payment_qs:
        ledger_events.append({
            'date': p.paid_at.date(),
            'description': f"Payment — {p.get_method_display()}" + (f" ({p.reference})" if p.reference else ''),
            'charge': None,
            'payment': float(p.amount_kes),
        })
    ledger_events.sort(key=lambda x: x['date'])

    # Compute running balance
    running = 0
    ledger = []
    for ev in ledger_events:
        if ev['charge']:
            running += ev['charge']
        if ev['payment']:
            running -= ev['payment']
        ledger.append({
            'date': ev['date'],
            'description': ev['description'],
            'charge': ev['charge'],
            'payment': ev['payment'],
            'balance': running,
        })

    period_invoiced = sum(ev['charge'] for ev in ledger if ev['charge'])
    period_paid = sum(ev['payment'] for ev in ledger if ev['payment'])
    period_balance = period_invoiced - period_paid

    return render(request, 'dashboard/parent_child_detail.html', {
        'child': child,
        'exam_summaries': exam_summaries,
        'present_30': present_30,
        'absent_30': absent_30,
        'late_30': late_30,
        'attendance_pct': attendance_pct,
        'invoices': invoices,
        'total_due': total_due,
        'fee_rows': fee_rows,
        'fee_total': fee_total,
        'period': period,
        'ledger': ledger,
        'period_invoiced': period_invoiced,
        'period_paid': period_paid,
        'period_balance': period_balance,
    })


@login_required
@school_staff_only
def add_parent(request):
    from apps.parents.models import Parent
    from apps.students.models import Student

    school = request.user.school
    all_students = Student.objects.filter(school=school, is_active=True).order_by('class_level', 'first_name')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        occupation = request.POST.get('occupation', '').strip()
        phone = request.POST.get('phone', '').strip()
        relationship = request.POST.get('relationship', 'guardian')
        student_ids = request.POST.getlist('students')   # list of selected student IDs
        photo = request.FILES.get('photo')

        errors = []
        if not email:
            errors.append('Email is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if not first_name or not last_name:
            errors.append('First and last name are required.')
        if User.objects.filter(email=email).exists():
            errors.append(f'Email "{email}" is already registered.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/add_parent.html', {
                'students': all_students,
                'relationships': Parent.Relationship.choices,
                'form_data': request.POST,
            })

        # Create the user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='parent',
            phone=phone,
            school=school,
        )

        # Create the parent profile
        parent = Parent.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            id_number=id_number,
            occupation=occupation,
            phone=phone,
            relationship=relationship,
            photo=photo,
        )

        # Link children
        if student_ids:
            students_to_link = Student.objects.filter(id__in=student_ids, school=school)
            parent.students.set(students_to_link)

        messages.success(
            request,
            f'✅ Parent "{parent.user.get_full_name()}" added'
            + (f' and linked to {parent.students.count()} student(s).' if student_ids else '.')
        )
        return redirect('parents_list')

    return render(request, 'dashboard/add_parent.html', {
        'students': all_students,
        'relationships': Parent.Relationship.choices,
    })


@login_required
@school_staff_only
def delete_parent(request, parent_id):
    from apps.parents.models import Parent

    parent = get_object_or_404(Parent, id=parent_id, user__school=request.user.school)

    if request.method == 'POST':
        name = parent.user.get_full_name() or parent.user.email
        # Delete the user (cascades to parent)
        parent.user.delete()
        messages.success(request, f'🗑️ Parent "{name}" deleted.')
        return redirect('parents_list')

    return render(request, 'dashboard/delete_parent.html', {'parent': parent})


@login_required
def link_parent_children(request, parent_id):
    """Link/Unlink students to a parent."""
    if request.user.role not in ('principal', 'secretary', 'super_admin'):
        return redirect('dashboard_home')

    from apps.parents.models import Parent
    from apps.students.models import Student

    parent = get_object_or_404(Parent, id=parent_id)
    school = parent.user.school if parent.user and parent.user.school else request.user.school
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    linked_student_ids = set(parent.students.values_list('id', flat=True))

    if request.method == 'POST':
        selected_student_ids = request.POST.getlist('students')
        selected_student_ids = [int(sid) for sid in selected_student_ids]
        parent.students.clear()
        for sid in selected_student_ids:
            try:
                student = Student.objects.get(id=sid, school=school)
                parent.students.add(student)
            except Student.DoesNotExist:
                pass

        messages.success(request, f'Updated student links for {parent.first_name} {parent.last_name}.')
        return redirect('parents_list')

    return render(request, 'dashboard/link_parent_children.html', {
        'parent': parent,
        'students': students,
        'linked_student_ids': linked_student_ids,
        'school': school,
    })

@login_required
@parent_only
def parent_child_statement_pdf(request, student_id):
    """Download a branded fee statement PDF for one child."""
    from apps.finance.models import Invoice, Payment
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from django.utils import timezone
    from datetime import timedelta

    # Security
    try:
        child = request.user.parent_profile.students.get(id=student_id)
    except Exception:
        messages.error(request, 'Child not found.')
        return redirect('parent_children')

    period = request.GET.get('period', 'term')
    now = timezone.now()
    if period == 'term':
        start = now - timedelta(days=90)
        period_label = 'Last 90 Days'
    elif period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        period_label = f'Year {now.year}'
    else:
        start = None
        period_label = 'All Time'

    invoice_qs = Invoice.objects.filter(student=child).select_related('fee_structure')
    payment_qs = Payment.objects.filter(invoice__student=child).select_related('invoice')

    if start:
        invoice_qs = invoice_qs.filter(created_at__gte=start)
        payment_qs = payment_qs.filter(paid_at__gte=start)

    # Build ledger
    events = []
    for inv in invoice_qs:
        events.append({
            'date': inv.created_at.date(),
            'description': f"Invoice — {inv.fee_structure.name if inv.fee_structure else 'Fee'}",
            'charge': float(inv.amount_due),
            'payment': None,
        })
    for p in payment_qs:
        events.append({
            'date': p.paid_at.date(),
            'description': f"Payment — {p.get_method_display()} {p.reference or ''}".strip(),
            'charge': None,
            'payment': float(p.amount_kes),
        })
    events.sort(key=lambda x: x['date'])

    running = 0
    ledger = []
    for ev in events:
        if ev['charge']: running += ev['charge']
        if ev['payment']: running -= ev['payment']
        ledger.append({**ev, 'balance': running})

    total_invoiced = sum(ev['charge'] for ev in events if ev['charge'])
    total_paid = sum(ev['payment'] for ev in events if ev['payment'])
    balance = total_invoiced - total_paid

    html_string = render_to_string('pdf/parent_statement.html',
        build_pdf_context(
            school=child.school,
            generated_by=request.user,
            child=child,
            parent=request.user,
            period_label=period_label,
            ledger=ledger,
            total_invoiced=total_invoiced,
            total_paid=total_paid,
            balance=balance,
        )
    )

    filename = f"statement_{child.admission_number}.pdf"
    return html_to_pdf_response(html_string, filename)


