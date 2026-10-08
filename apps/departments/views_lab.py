"""
Laboratory / Lab Technician module views.
Lab Tech manages equipment, incidents, and practicals.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from .models import LabEquipment, LabIncident, PracticalSchedule


def _lab_required(request):
    """Lab Tech or School Admin can access lab pages."""
    return request.user.role in ('lab_technician', 'principal')


def _lab_only(request):
    """Only Lab Tech can manage lab data (CRUD)."""
    return request.user.role == 'lab_technician'


# ============================================================
# LAB DASHBOARD
# ============================================================

@login_required
def lab_dashboard(request):
    """Lab Technician's main dashboard."""
    if not _lab_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Equipment stats
    equipment = LabEquipment.objects.filter(school=school, is_active=True)
    total_items = equipment.count()
    total_quantity = sum(e.quantity for e in equipment)
    working = sum(e.working_quantity for e in equipment)
    broken_or_repair = [e for e in equipment if e.condition in ('broken', 'needs_repair')]
    total_value = sum(e.total_value for e in equipment)

    # Recent incidents
    recent_incidents = LabIncident.objects.filter(
        school=school
    ).select_related('equipment', 'involved_student').order_by('-incident_date')[:10]

    unresolved = LabIncident.objects.filter(
        school=school, resolved=False
    ).count()

    # Upcoming practicals
    upcoming_practicals = PracticalSchedule.objects.filter(
        school=school,
        scheduled_date__gte=today,
        is_completed=False,
    ).order_by('scheduled_date', 'start_time')[:10]

    # Today's practicals
    today_practicals = PracticalSchedule.objects.filter(
        school=school, scheduled_date=today
    ).order_by('start_time')

    return render(request, 'departments/lab/dashboard.html', {
        'today': today,
        'total_items': total_items,
        'total_quantity': total_quantity,
        'working': working,
        'broken_or_repair': broken_or_repair,
        'total_value': total_value,
        'recent_incidents': recent_incidents,
        'unresolved': unresolved,
        'upcoming_practicals': upcoming_practicals,
        'today_practicals': today_practicals,
    })


# ============================================================
# EQUIPMENT
# ============================================================

@login_required
def lab_equipment_list(request):
    """List all lab equipment."""
    if not _lab_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = LabEquipment.objects.filter(school=school).order_by('category', 'name')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(location__icontains=search) |
            Q(supplier__icontains=search)
        )

    category = request.GET.get('category', '')
    if category:
        qs = qs.filter(category=category)

    condition = request.GET.get('condition', '')
    if condition:
        qs = qs.filter(condition=condition)

    items = list(qs)
    broken = [i for i in items if i.condition in ('broken', 'needs_repair')]
    total_value = sum(i.total_value for i in items)

    return render(request, 'departments/lab/equipment_list.html', {
        'items': items,
        'broken': broken,
        'total_value': total_value,
        'search': search,
        'category_filter': category,
        'condition_filter': condition,
        'categories': LabEquipment.CATEGORY_CHOICES,
        'conditions': LabEquipment.CONDITION_CHOICES,
    })


@login_required
def lab_equipment_form(request, item_id=None):
    """Add or edit lab equipment."""
    if not _lab_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    item = None
    if item_id:
        item = get_object_or_404(LabEquipment, id=item_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', 'other').strip()
        quantity = request.POST.get('quantity', '1').strip() or '1'
        working_quantity = request.POST.get('working_quantity', quantity).strip() or quantity
        condition = request.POST.get('condition', 'good').strip()
        location = request.POST.get('location', '').strip()
        purchase_date = request.POST.get('purchase_date') or None
        unit_cost = request.POST.get('unit_cost', '0').strip() or '0'
        supplier = request.POST.get('supplier', '').strip()
        notes = request.POST.get('notes', '').strip()
        is_active = 'is_active' in request.POST

        errors = []
        if not name:
            errors.append('Equipment name is required.')

        existing = LabEquipment.objects.filter(school=school, name=name)
        if item:
            existing = existing.exclude(id=item.id)
        if existing.exists():
            errors.append(f'"{name}" already exists in inventory.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/lab/equipment_form.html', {
                'item': item,
                'form_data': request.POST,
                'categories': LabEquipment.CATEGORY_CHOICES,
                'conditions': LabEquipment.CONDITION_CHOICES,
            })

        if item:
            item.name = name
            item.category = category
            item.quantity = quantity
            item.working_quantity = working_quantity
            item.condition = condition
            item.location = location
            item.purchase_date = purchase_date
            item.unit_cost = unit_cost
            item.supplier = supplier
            item.notes = notes
            item.is_active = is_active
            item.save()
            messages.success(request, f'"{name}" updated.')
        else:
            LabEquipment.objects.create(
                school=school,
                name=name,
                category=category,
                quantity=quantity,
                working_quantity=working_quantity,
                condition=condition,
                location=location,
                purchase_date=purchase_date,
                unit_cost=unit_cost,
                supplier=supplier,
                notes=notes,
                is_active=is_active,
            )
            messages.success(request, f'"{name}" added to inventory.')

        return redirect('lab_equipment_list')

    return render(request, 'departments/lab/equipment_form.html', {
        'item': item,
        'categories': LabEquipment.CATEGORY_CHOICES,
        'conditions': LabEquipment.CONDITION_CHOICES,
    })


@login_required
def lab_equipment_delete(request, item_id):
    """Delete equipment."""
    if not _lab_only(request):
        return redirect('dashboard_home')

    item = get_object_or_404(LabEquipment, id=item_id, school=request.user.school)

    if request.method == 'POST':
        name = item.name
        item.delete()
        messages.success(request, f'"{name}" deleted.')
        return redirect('lab_equipment_list')

    return render(request, 'departments/lab/confirm_delete.html', {
        'object_name': item.name,
        'object_type': 'Equipment',
        'cancel_url': 'lab_equipment_list',
    })


# ============================================================
# INCIDENTS
# ============================================================

@login_required
def lab_incident_list(request):
    """List lab incidents."""
    if not _lab_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = LabIncident.objects.filter(school=school).select_related(
        'equipment', 'involved_student', 'reported_by'
    ).order_by('-incident_date', '-created_at')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(class_involved__icontains=search))

    incident_type = request.GET.get('type', '')
    if incident_type:
        qs = qs.filter(incident_type=incident_type)

    severity = request.GET.get('severity', '')
    if severity:
        qs = qs.filter(severity=severity)

    status = request.GET.get('status', '')
    if status == 'open':
        qs = qs.filter(resolved=False)
    elif status == 'resolved':
        qs = qs.filter(resolved=True)

    return render(request, 'departments/lab/incident_list.html', {
        'incidents': qs,
        'search': search,
        'type_filter': incident_type,
        'severity_filter': severity,
        'status_filter': status,
        'incident_types': LabIncident.INCIDENT_CHOICES,
        'severities': LabIncident.SEVERITY_CHOICES,
    })


@login_required
def lab_incident_form(request, incident_id=None):
    """Log or edit a lab incident."""
    if not _lab_only(request):
        return redirect('dashboard_home')

    from apps.students.models import Student

    school = request.user.school
    incident = None
    if incident_id:
        incident = get_object_or_404(LabIncident, id=incident_id, school=school)

    equipment_list = LabEquipment.objects.filter(school=school, is_active=True).order_by('name')
    students = Student.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')

    if request.method == 'POST':
        incident_type = request.POST.get('incident_type', '').strip()
        incident_date = request.POST.get('incident_date', '').strip()
        incident_time = request.POST.get('incident_time') or None
        equipment_id = request.POST.get('equipment') or None
        student_id = request.POST.get('involved_student') or None
        class_involved = request.POST.get('class_involved', '').strip()
        severity = request.POST.get('severity', 'low').strip()
        description = request.POST.get('description', '').strip()
        action_taken = request.POST.get('action_taken', '').strip()
        resolved = 'resolved' in request.POST

        errors = []
        if not incident_type:
            errors.append('Incident type is required.')
        if not incident_date:
            errors.append('Incident date is required.')
        if not description:
            errors.append('Description is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/lab/incident_form.html', {
                'incident': incident,
                'equipment_list': equipment_list,
                'students': students,
                'form_data': request.POST,
                'incident_types': LabIncident.INCIDENT_CHOICES,
                'severities': LabIncident.SEVERITY_CHOICES,
                'today': date.today(),
            })

        if incident:
            incident.incident_type = incident_type
            incident.incident_date = incident_date
            incident.incident_time = incident_time
            incident.equipment_id = equipment_id
            incident.involved_student_id = student_id
            incident.class_involved = class_involved
            incident.severity = severity
            incident.description = description
            incident.action_taken = action_taken
            if resolved and not incident.resolved:
                incident.resolved = True
                incident.resolved_at = timezone.now()
            elif not resolved:
                incident.resolved = False
                incident.resolved_at = None
            incident.save()
            messages.success(request, 'Incident updated.')
        else:
            LabIncident.objects.create(
                school=school,
                incident_type=incident_type,
                incident_date=incident_date,
                incident_time=incident_time,
                equipment_id=equipment_id,
                involved_student_id=student_id,
                class_involved=class_involved,
                severity=severity,
                description=description,
                action_taken=action_taken,
                reported_by=request.user,
                resolved=resolved,
                resolved_at=timezone.now() if resolved else None,
            )
            messages.success(request, 'Incident recorded.')

        return redirect('lab_incident_list')

    return render(request, 'departments/lab/incident_form.html', {
        'incident': incident,
        'equipment_list': equipment_list,
        'students': students,
        'incident_types': LabIncident.INCIDENT_CHOICES,
        'severities': LabIncident.SEVERITY_CHOICES,
        'today': date.today(),
    })


# ============================================================
# PRACTICALS
# ============================================================

@login_required
def practical_list(request):
    """List all practical schedules."""
    if not _lab_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    qs = PracticalSchedule.objects.filter(school=school).order_by('-scheduled_date', 'start_time')

    search = request.GET.get('q', '').strip()
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(class_level__icontains=search))

    status = request.GET.get('status', '')
    if status == 'upcoming':
        qs = qs.filter(scheduled_date__gte=date.today(), is_completed=False)
    elif status == 'completed':
        qs = qs.filter(is_completed=True)

    return render(request, 'departments/lab/practical_list.html', {
        'practicals': qs[:100],
        'search': search,
        'status_filter': status,
        'today': date.today(),
    })


@login_required
def practical_form(request, practical_id=None):
    """Schedule or edit a practical."""
    if not _lab_only(request):
        return redirect('dashboard_home')

    school = request.user.school
    practical = None
    if practical_id:
        practical = get_object_or_404(PracticalSchedule, id=practical_id, school=school)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        class_level = request.POST.get('class_level', '').strip()
        subject = request.POST.get('subject', '').strip()
        scheduled_date = request.POST.get('scheduled_date', '').strip()
        start_time = request.POST.get('start_time') or None
        end_time = request.POST.get('end_time') or None
        equipment_needed = request.POST.get('equipment_needed', '').strip()
        teacher = request.POST.get('teacher', '').strip()
        notes = request.POST.get('notes', '').strip()
        is_completed = 'is_completed' in request.POST

        errors = []
        if not title:
            errors.append('Title is required.')
        if not class_level:
            errors.append('Class is required.')
        if not scheduled_date:
            errors.append('Date is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/lab/practical_form.html', {
                'practical': practical,
                'form_data': request.POST,
                'today': date.today(),
            })

        if practical:
            practical.title = title
            practical.class_level = class_level
            practical.subject = subject
            practical.scheduled_date = scheduled_date
            practical.start_time = start_time
            practical.end_time = end_time
            practical.equipment_needed = equipment_needed
            practical.teacher = teacher
            practical.notes = notes
            practical.is_completed = is_completed
            practical.save()
            messages.success(request, 'Practical updated.')
        else:
            PracticalSchedule.objects.create(
                school=school,
                title=title,
                class_level=class_level,
                subject=subject,
                scheduled_date=scheduled_date,
                start_time=start_time,
                end_time=end_time,
                equipment_needed=equipment_needed,
                teacher=teacher,
                notes=notes,
                is_completed=is_completed,
                created_by=request.user,
            )
            messages.success(request, 'Practical scheduled.')

        return redirect('practical_list')

    return render(request, 'departments/lab/practical_form.html', {
        'practical': practical,
        'today': date.today(),
    })


@login_required
def practical_delete(request, practical_id):
    """Delete a practical."""
    if not _lab_only(request):
        return redirect('dashboard_home')

    practical = get_object_or_404(PracticalSchedule, id=practical_id, school=request.user.school)

    if request.method == 'POST':
        practical.delete()
        messages.success(request, 'Practical deleted.')
        return redirect('practical_list')

    return render(request, 'departments/lab/confirm_delete.html', {
        'object_name': practical.title,
        'object_type': 'Practical',
        'cancel_url': 'practical_list',
    })


# ============================================================
# REPORTS
# ============================================================

@login_required
def lab_report_pdf(request):
    """PDF report of lab equipment + incidents."""
    if not _lab_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from apps.core.pdf_utils import image_to_base64
    import io

    school = request.user.school
    today = date.today()

    equipment = LabEquipment.objects.filter(school=school, is_active=True).order_by('category', 'name')

    # Last 30 days incidents
    thirty_ago = today - timedelta(days=30)
    incidents = LabIncident.objects.filter(
        school=school, incident_date__gte=thirty_ago
    ).select_related('equipment', 'involved_student').order_by('-incident_date')

    total_value = sum(e.total_value for e in equipment)

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    html_string = render_to_string('departments/lab/lab_report_pdf.html', {
        'school': school,
        'equipment': equipment,
        'incidents': incidents,
        'total_value': total_value,
        'today': today,
        'school_logo_b64': school_logo_b64,
        'user': request.user,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'lab_report_{today}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(src=io.StringIO(html_string), dest=response, encoding='utf-8')
    return response