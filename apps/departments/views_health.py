"""
Health / Nurse module views.
Nurse manages visits, medicine, and reports.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import HealthVisit, Medicine, MedicineLog, DepartmentChoices


def _nurse_required(request):
    """Nurse or School Admin can access health pages."""
    return request.user.role in ('nurse', 'principal')


def _nurse_only(request):
    """Only Nurse can manage health data (CRUD)."""
    return request.user.role == 'nurse'


# ============================================================
# NURSE DASHBOARD
# ============================================================

@login_required
def nurse_dashboard(request):
    """Nurse's main dashboard."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Stats
    today_visits = HealthVisit.objects.filter(school=school, visit_date=today).count()
    total_visits = HealthVisit.objects.filter(school=school).count()
    this_week = HealthVisit.objects.filter(
        school=school, visit_date__gte=today - timedelta(days=7)
    ).count()

    # Medicine alerts
    low_stock = Medicine.objects.filter(
        school=school, is_active=True
    ).filter(quantity__lte=models.F('reorder_level')) if False else []

    medicines = Medicine.objects.filter(school=school, is_active=True)
    low_stock = [m for m in medicines if m.is_low_stock]
    expiring = [m for m in medicines if m.is_expiring_soon and not m.is_expired]
    expired = [m for m in medicines if m.is_expired]

    # Recent visits
    recent_visits = HealthVisit.objects.filter(
        school=school
    ).select_related('student').order_by('-visit_date', '-created_at')[:10]

    # Referrals (last 30 days)
    referrals = HealthVisit.objects.filter(
        school=school,
        outcome='referred',
        visit_date__gte=today - timedelta(days=30),
    ).select_related('student').order_by('-visit_date')[:10]

    return render(request, 'departments/nurse/dashboard.html', {
        'today_visits': today_visits,
        'total_visits': total_visits,
        'this_week': this_week,
        'low_stock': low_stock,
        'expiring': expiring,
        'expired': expired,
        'recent_visits': recent_visits,
        'referrals': referrals,
        'today': today,
    })


# ============================================================
# HEALTH VISITS
# ============================================================

@login_required
def health_visit_list(request):
    """List all health visits."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = HealthVisit.objects.filter(school=school).select_related('student', 'attended_by')

    # Filters
    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__admission_number__icontains=search) |
            Q(symptoms__icontains=search) |
            Q(diagnosis__icontains=search)
        )

    visit_type = request.GET.get('type', '')
    if visit_type:
        qs = qs.filter(visit_type=visit_type)

    outcome = request.GET.get('outcome', '')
    if outcome:
        qs = qs.filter(outcome=outcome)

    qs = qs.order_by('-visit_date', '-created_at')

    # Stats
    stats = {
        'total': qs.count(),
        'illness': qs.filter(visit_type='illness').count(),
        'injury': qs.filter(visit_type='injury').count(),
        'referred': qs.filter(outcome='referred').count(),
    }

    return render(request, 'departments/nurse/visit_list.html', {
        'visits': qs[:200],
        'stats': stats,
        'search': search,
        'visit_type_filter': visit_type,
        'outcome_filter': outcome,
    })


@login_required
def health_visit_form(request, visit_id=None):
    """Log a new health visit (or edit)."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from datetime import datetime

    school = request.user.school

    visit = None
    if visit_id:
        visit = get_object_or_404(HealthVisit, id=visit_id, school=school)

    students = Student.objects.filter(
        school=school, is_active=True
    ).order_by('first_name', 'last_name')

    medicines = Medicine.objects.filter(
        school=school, is_active=True
    ).order_by('name')

    if request.method == 'POST':
        student_id = request.POST.get('student', '').strip()
        visit_date = request.POST.get('visit_date', '').strip()
        visit_time = request.POST.get('visit_time') or None
        visit_type = request.POST.get('visit_type', 'illness').strip()
        symptoms = request.POST.get('symptoms', '').strip()
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        outcome = request.POST.get('outcome', 'treated').strip()
        referred_to = request.POST.get('referred_to', '').strip()
        guardian_notified = 'guardian_notified' in request.POST
        notes = request.POST.get('notes', '').strip()

        # Medicine dispensed (list of (medicine_id, quantity))
        dispensed = []
        for key in request.POST:
            if key.startswith('dispense_') and request.POST[key]:
                med_id = key.replace('dispense_', '')
                qty = request.POST[key].strip()
                if qty.isdigit() and int(qty) > 0:
                    dispensed.append((int(med_id), int(qty)))

        errors = []
        if not student_id:
            errors.append('Student is required.')
        if not visit_date:
            errors.append('Visit date is required.')
        if not symptoms:
            errors.append('Symptoms are required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/nurse/visit_form.html', {
                'visit': visit,
                'students': students,
                'medicines': medicines,
                'today': date.today(),
                'form_data': request.POST,
            })

        if visit:
            visit.student_id = student_id
            visit.visit_date = visit_date
            visit.visit_time = visit_time
            visit.visit_type = visit_type
            visit.symptoms = symptoms
            visit.diagnosis = diagnosis
            visit.treatment = treatment
            visit.outcome = outcome
            visit.referred_to = referred_to
            visit.guardian_notified = guardian_notified
            if guardian_notified and not visit.guardian_notified_at:
                visit.guardian_notified_at = timezone.now()
            visit.notes = notes
            visit.save()
            messages.success(request, 'Visit updated.')
        else:
            visit = HealthVisit.objects.create(
                school=school,
                student_id=student_id,
                visit_date=visit_date,
                visit_time=visit_time,
                visit_type=visit_type,
                symptoms=symptoms,
                diagnosis=diagnosis,
                treatment=treatment,
                outcome=outcome,
                referred_to=referred_to,
                guardian_notified=guardian_notified,
                guardian_notified_at=timezone.now() if guardian_notified else None,
                attended_by=request.user,
                notes=notes,
            )
            messages.success(request, 'Visit recorded.')

            # Process medicine dispensation
            for med_id, qty in dispensed:
                try:
                    med = Medicine.objects.get(id=med_id, school=school)
                    if med.quantity >= qty:
                        med.quantity -= qty
                        med.save()
                        MedicineLog.objects.create(
                            school=school,
                            medicine=med,
                            action='out',
                            quantity=qty,
                            balance_after=med.quantity,
                            related_visit=visit,
                            reason=f'Dispensed for {visit.student.full_name}',
                            recorded_by=request.user,
                        )
                    else:
                        messages.warning(
                            request,
                            f'Insufficient {med.name}: {med.quantity} left, tried to dispense {qty}'
                        )
                except Medicine.DoesNotExist:
                    continue

        return redirect('health_visit_list')

    return render(request, 'departments/nurse/visit_form.html', {
        'visit': visit,
        'students': students,
        'medicines': medicines,
        'today': date.today(),
    })


@login_required
def health_visit_detail(request, visit_id):
    """View a single visit."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    visit = get_object_or_404(HealthVisit, id=visit_id, school=request.user.school)
    logs = visit.medicine_logs.select_related('medicine').order_by('-created_at')

    return render(request, 'departments/nurse/visit_detail.html', {
        'visit': visit,
        'medicine_logs': logs,
    })


# ============================================================
# MEDICINE STOCK
# ============================================================

@login_required
def medicine_list(request):
    """List all medicines."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = Medicine.objects.filter(school=school).order_by('name')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(supplier__icontains=search)
        )

    category = request.GET.get('category', '')
    if category:
        qs = qs.filter(category=category)

    medicines = list(qs)
    low_stock = [m for m in medicines if m.is_low_stock]
    expiring = [m for m in medicines if m.is_expiring_soon and not m.is_expired]
    expired = [m for m in medicines if m.is_expired]

    return render(request, 'departments/nurse/medicine_list.html', {
        'medicines': medicines,
        'low_stock': low_stock,
        'expiring': expiring,
        'expired': expired,
        'search': search,
        'category_filter': category,
        'categories': Medicine.CATEGORY_CHOICES,
    })


@login_required
def medicine_form(request, medicine_id=None):
    """Add or edit a medicine."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    medicine = None
    if medicine_id:
        medicine = get_object_or_404(Medicine, id=medicine_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', 'other').strip()
        unit = request.POST.get('unit', '').strip()
        quantity = request.POST.get('quantity', '0').strip()
        reorder_level = request.POST.get('reorder_level', '10').strip()
        expiry_date = request.POST.get('expiry_date') or None
        supplier = request.POST.get('supplier', '').strip()
        notes = request.POST.get('notes', '').strip()
        is_active = 'is_active' in request.POST

        errors = []
        if not name:
            errors.append('Medicine name is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/nurse/medicine_form.html', {
                'medicine': medicine,
                'form_data': request.POST,
                'categories': Medicine.CATEGORY_CHOICES,
            })

        if medicine:
            old_qty = medicine.quantity
            medicine.name = name
            medicine.category = category
            medicine.unit = unit
            medicine.reorder_level = reorder_level or 10
            medicine.expiry_date = expiry_date
            medicine.supplier = supplier
            medicine.notes = notes
            medicine.is_active = is_active

            # If quantity changed, log it
            new_qty = int(quantity or 0)
            if new_qty != old_qty:
                medicine.quantity = new_qty
                medicine.save()
                MedicineLog.objects.create(
                    school=school,
                    medicine=medicine,
                    action='adjust',
                    quantity=abs(new_qty - old_qty),
                    balance_after=new_qty,
                    reason=f'Manual adjustment ({old_qty} → {new_qty})',
                    recorded_by=request.user,
                )
            else:
                medicine.save()

            messages.success(request, f'Medicine "{name}" updated.')
        else:
            qty = int(quantity or 0)
            med = Medicine.objects.create(
                school=school,
                name=name,
                category=category,
                unit=unit,
                quantity=qty,
                reorder_level=reorder_level or 10,
                expiry_date=expiry_date,
                supplier=supplier,
                notes=notes,
                is_active=is_active,
            )
            if qty > 0:
                MedicineLog.objects.create(
                    school=school,
                    medicine=med,
                    action='in',
                    quantity=qty,
                    balance_after=qty,
                    reason='Initial stock',
                    recorded_by=request.user,
                )
            messages.success(request, f'Medicine "{name}" added.')

        return redirect('medicine_list')

    return render(request, 'departments/nurse/medicine_form.html', {
        'medicine': medicine,
        'categories': Medicine.CATEGORY_CHOICES,
    })


@login_required
def medicine_stock_in(request, medicine_id):
    """Record stock in (purchase/receive)."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    medicine = get_object_or_404(Medicine, id=medicine_id, school=request.user.school)

    if request.method == 'POST':
        qty = request.POST.get('quantity', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not qty or not qty.isdigit() or int(qty) <= 0:
            messages.error(request, 'Please enter a valid quantity.')
        else:
            qty = int(qty)
            medicine.quantity += qty
            medicine.save()

            MedicineLog.objects.create(
                school=request.user.school,
                medicine=medicine,
                action='in',
                quantity=qty,
                balance_after=medicine.quantity,
                reason=reason or 'Stock received',
                recorded_by=request.user,
            )
            messages.success(request, f'{qty} {medicine.unit} of {medicine.name} added.')
            return redirect('medicine_list')

    return render(request, 'departments/nurse/medicine_stock.html', {
        'medicine': medicine,
        'action': 'in',
    })


@login_required
def medicine_stock_out(request, medicine_id):
    """Record stock out (dispense/remove)."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    medicine = get_object_or_404(Medicine, id=medicine_id, school=request.user.school)

    if request.method == 'POST':
        qty = request.POST.get('quantity', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not qty or not qty.isdigit() or int(qty) <= 0:
            messages.error(request, 'Please enter a valid quantity.')
        elif int(qty) > medicine.quantity:
            messages.error(request, f'Only {medicine.quantity} {medicine.unit} available.')
        else:
            qty = int(qty)
            medicine.quantity -= qty
            medicine.save()

            MedicineLog.objects.create(
                school=request.user.school,
                medicine=medicine,
                action='out',
                quantity=qty,
                balance_after=medicine.quantity,
                reason=reason or 'Dispensed',
                recorded_by=request.user,
            )
            messages.success(request, f'{qty} {medicine.unit} of {medicine.name} dispensed.')
            return redirect('medicine_list')

    return render(request, 'departments/nurse/medicine_stock.html', {
        'medicine': medicine,
        'action': 'out',
    })


@login_required
def medicine_logs(request, medicine_id=None):
    """View all medicine stock movements."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = MedicineLog.objects.filter(school=school).select_related(
        'medicine', 'recorded_by', 'related_visit'
    ).order_by('-created_at')

    medicine = None
    if medicine_id:
        medicine = get_object_or_404(Medicine, id=medicine_id, school=school)
        qs = qs.filter(medicine=medicine)

    action_filter = request.GET.get('action', '')
    if action_filter:
        qs = qs.filter(action=action_filter)

    return render(request, 'departments/nurse/medicine_logs.html', {
        'logs': qs[:200],
        'medicine': medicine,
        'action_filter': action_filter,
        'action_choices': MedicineLog.ACTION_CHOICES,
    })


# ============================================================
# REPORTS
# ============================================================

@login_required
def health_report_pdf(request):
    """PDF report of health visits."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from apps.core.pdf_utils import image_to_base64
    import io

    school = request.user.school

    # Date range
    days = int(request.GET.get('days', 30))
    since = date.today() - timedelta(days=days)

    visits = HealthVisit.objects.filter(
        school=school, visit_date__gte=since
    ).select_related('student', 'attended_by').order_by('-visit_date')

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    html_string = render_to_string('departments/nurse/health_report_pdf.html', {
        'school': school,
        'visits': visits,
        'since': since,
        'today': date.today(),
        'days': days,
        'total': visits.count(),
        'school_logo_b64': school_logo_b64,
        'user': request.user,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'health_report_{date.today()}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    pisa.CreatePDF(src=io.StringIO(html_string), dest=response, encoding='utf-8')
    return response

# ==========================================================
# REFERRAL TO FACILITY
# ==========================================================

@login_required
def refer_to_facility(request, visit_id):
    """Mark a visit as referred and generate a referral note."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    visit = get_object_or_404(
        HealthVisit, id=visit_id, school=request.user.school
    )

    if request.method == 'POST':
        visit.outcome = 'referred'
        visit.referred_to = request.POST.get('facility_name', '').strip()
        visit.notes = request.POST.get('referral_reason', '').strip()
        visit.guardian_notified = 'guardian_notified' in request.POST
        visit.save()

        messages.success(request, f"Visit marked as referred to {visit.referred_to}.")
        return redirect('health_visit_detail', visit_id=visit.id)

    return render(request, 'departments/nurse/refer_form.html', {
        'visit': visit,
    })


@login_required
def referral_note_pdf(request, visit_id):
    """Printable referral note PDF for the parent to take to the hospital."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    visit = get_object_or_404(HealthVisit, id=visit_id, school=request.user.school)

    from apps.core.pdf_utils import html_to_pdf_response, build_pdf_context
    from django.template.loader import render_to_string

    context = build_pdf_context(
        request.user.school, request.user,
        visit=visit,
        student=visit.student,
    )
    html_string = render_to_string('pdf/nurse_referral_note.html', context)
    return html_to_pdf_response(
        html_string,
        f'referral_{visit.student.admission_number}_{visit.id}.pdf',
    )


# ==========================================================
# MEDICAL REPORT PDF (per student, per period)
# ==========================================================

@login_required
def student_medical_report_pdf(request, student_id):
    """Medical report for one student over a period."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from datetime import date, timedelta

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    period = request.GET.get('period', 'month').strip()
    today = date.today()

    if period == 'today':
        start = today; label = 'Today'
    elif period == 'week':
        start = today - timedelta(days=7); label = 'Last 7 Days'
    elif period == 'month':
        start = today.replace(day=1); label = 'This Month'
    elif period == 'term':
        start = today - timedelta(days=90); label = 'Last 90 Days (Term)'
    elif period == 'year':
        start = today.replace(month=1, day=1); label = 'This Year'
    else:
        start = today.replace(day=1); label = 'This Month'

    visits = HealthVisit.objects.filter(
        school=request.user.school, student=student,
        visit_date__gte=start, visit_date__lte=today,
    ).order_by('-visit_date')

    from apps.core.pdf_utils import html_to_pdf_response, build_pdf_context
    from django.template.loader import render_to_string

    context = build_pdf_context(
        request.user.school, request.user,
        student=student, visits=visits,
        period_label=label, period_start=start, period_end=today,
    )
    html_string = render_to_string('pdf/nurse_medical_report.html', context)
    return html_to_pdf_response(
        html_string,
        f'medical_report_{student.admission_number}_{period}.pdf',
    )


# ==========================================================
# MEDICINE ISSUE LOG PDF
# ==========================================================

@login_required
def medicine_log_pdf(request, medicine_id):
    """Audit log of one medicine — every issue with date, student, quantity."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    medicine = get_object_or_404(Medicine, id=medicine_id, school=request.user.school)

    logs = MedicineLog.objects.filter(
        school=request.user.school, medicine=medicine
    ).select_related('related_visit__student', 'recorded_by').order_by('-created_at')
    from apps.core.pdf_utils import html_to_pdf_response, build_pdf_context
    from django.template.loader import render_to_string

    context = build_pdf_context(
        request.user.school, request.user,
        medicine=medicine, logs=logs,
    )
    html_string = render_to_string('pdf/nurse_medicine_log.html', context)
    return html_to_pdf_response(
        html_string,
        f'medicine_log_{medicine.id}.pdf',
    )