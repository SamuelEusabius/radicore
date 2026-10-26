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
    """Nurse's main dashboard with Waiting Room."""
    if not _nurse_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # 1. Waiting Room (Students currently in the clinic)
    waiting_visits = HealthVisit.objects.filter(
        school=school, 
        status__in=['waiting', 'in_treatment']
    ).select_related('student').order_by('visit_date', 'visit_time')

    # 2. Discharged Today
    discharged_today = HealthVisit.objects.filter(
        school=school, 
        status='discharged',
        visit_date=today
    ).select_related('student')

    # 3. Medicine alerts
    medicines = Medicine.objects.filter(school=school, is_active=True)
    low_stock = [m for m in medicines if m.is_low_stock]
    expiring = [m for m in medicines if m.is_expiring_soon and not m.is_expired]
    expired = [m for m in medicines if m.is_expired]

    # 4. Recent visits (History)
    recent_visits = HealthVisit.objects.filter(
        school=school
    ).select_related('student').order_by('-visit_date', '-created_at')[:10]

    return render(request, 'departments/nurse/dashboard.html', {
        'waiting_visits': waiting_visits,
        'discharged_today': discharged_today,
        'low_stock': low_stock,
        'expiring': expiring,
        'expired': expired,
        'recent_visits': recent_visits,
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
    """Log a new student into the clinic, or update an existing one."""
    if not _nurse_only(request):
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school
    visit = get_object_or_404(HealthVisit, id=visit_id, school=school) if visit_id else None
    students = Student.objects.filter(school=school, is_active=True).only(
        'id', 'first_name', 'last_name', 'admission_number', 'class_level'
    ).order_by('first_name', 'last_name')
    
    medicines = Medicine.objects.filter(school=school, is_active=True).only(
        'id', 'name', 'quantity', 'unit'
    ).order_by('name')

    if request.method == 'POST':
        student_id = request.POST.get('student')
        student = get_object_or_404(Student, id=student_id, school=school)

        if not visit:
            visit = HealthVisit(school=school, student=student, attended_by=request.user)
        
        # Triage Data
        visit.temperature = request.POST.get('temperature') or None
        visit.blood_pressure = request.POST.get('blood_pressure')
        visit.weight_kg = request.POST.get('weight_kg') or None
        visit.pulse_rate = request.POST.get('pulse_rate') or None
        
        visit.symptoms = request.POST.get('symptoms')
        visit.diagnosis = request.POST.get('diagnosis')
        visit.treatment = request.POST.get('treatment')
        visit.notes = request.POST.get('notes')
        
        # Status
        new_status = request.POST.get('status', 'waiting')
        visit.status = new_status
        if new_status == 'discharged':
            visit.outcome = 'Treated and discharged'

        visit.save()
        messages.success(request, f"Clinic record for {student.first_name} updated.")
        
        if new_status == 'discharged':
            return redirect('nurse_dashboard')
        return redirect('health_visit_detail', visit_id=visit.id)

    return render(request, 'departments/nurse/visit_form.html', {
        'visit': visit,
        'students': students,
        'medicines': medicines,
    })

@login_required
def health_visit_detail(request, visit_id):
    """View full medical record, dispense medicine, and handle referrals."""
    if not _nurse_required(request):
        return redirect('dashboard_home')
        
    school = request.user.school
    visit = get_object_or_404(HealthVisit, id=visit_id, school=school)
    medicines = Medicine.objects.filter(school=school, quantity__gt=0)
    
    if request.method == 'POST':
        # Handle dispensing medicine
        if 'dispense_medicine' in request.POST:
            med_id = request.POST.get('medicine')
            qty = int(request.POST.get('quantity', 1))
            
            medicine = get_object_or_404(Medicine, id=med_id, school=school)
            if medicine.quantity >= qty:
                medicine.quantity -= qty
                medicine.save()
                
                MedicineLog.objects.create(
                    school=school,
                    medicine=medicine,
                    action='out',
                    quantity=qty,
                    balance_after=medicine.quantity,
                    related_visit=visit,
                    reason=f"Dispensed for visit #{visit.id}",
                    recorded_by=request.user
                )
                messages.success(request, f"Dispensed {qty} {medicine.unit} of {medicine.name}.")
            else:
                messages.error(request, "Not enough stock available.")
                
            return redirect('health_visit_detail', visit_id=visit.id)

        # Handle Referral to Facility
        elif 'refer_facility' in request.POST:
            facility_name = request.POST.get('facility_name')
            reason = request.POST.get('referral_reason')
            
            visit.status = 'referred_hosp'
            visit.outcome = 'referred'
            visit.referred_to = facility_name
            visit.notes = f"REFFERAL: {reason}\n\n{visit.notes or ''}"
            visit.save()
            
            messages.success(request, f"{visit.student.first_name} referred to {facility_name}.")
            return redirect('nurse_dashboard')

    # Get logs for this specific visit
    dispensed_logs = MedicineLog.objects.filter(related_visit=visit).select_related('medicine')

    return render(request, 'departments/nurse/visit_detail.html', {
        'visit': visit,
        'medicines': medicines,
        'dispensed_logs': dispensed_logs,
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
    school = request.user.school
    if school.logo:
        context['school_logo_url'] = request.build_absolute_uri(school.logo.url)
    else:
        context['school_logo_url'] = None

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