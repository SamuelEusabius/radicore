from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q

from .models import (
    Trip, TripStudent, Route, Vehicle, FuelLog, PreTripChecklist,
    DepartmentReport, DepartmentChoices,
)


def _driver_required(request):
    """Return True if user is a driver or admin."""
    return request.user.role in ('driver', 'school_admin', 'super_admin')


@login_required
def driver_dashboard(request):
    """Driver's main dashboard — today's trips + quick stats."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    today = date.today()

    # Today's trips for this driver
    today_trips = Trip.objects.filter(
        school=school,
        driver=request.user,
        date=today,
    ).order_by('direction')

    # Upcoming week trips
    upcoming = Trip.objects.filter(
        school=school,
        driver=request.user,
        date__gt=today,
        date__lte=today + timedelta(days=7),
    ).order_by('date', 'direction')[:10]

    # Fuel stats (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    fuel_qs = FuelLog.objects.filter(
        school=school,
        driver=request.user,
        date__gte=thirty_days_ago,
    )
    fuel_total = fuel_qs.aggregate(total=Sum('amount_kes'))['total'] or 0

    # Recent fuel logs
    recent_fuel = fuel_qs.order_by('-date', '-created_at')[:5]

    # My recent reports
    recent_reports = DepartmentReport.objects.filter(
        school=school,
        submitted_by=request.user,
    ).order_by('-report_date')[:5]

    return render(request, 'departments/driver/dashboard.html', {
        'today': today,
        'today_trips': today_trips,
        'upcoming_trips': upcoming,
        'fuel_total_30d': fuel_total,
        'recent_fuel': recent_fuel,
        'recent_reports': recent_reports,
        'today_trip_count': today_trips.count(),
    })


@login_required
def trip_detail(request, trip_id):
    """View a trip's details + student manifest."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trip = get_object_or_404(
        Trip, id=trip_id,
        school=request.user.school,
        driver=request.user,
    )
    trip_students = trip.trip_students.select_related(
        'student', 'student__current_class'
    ).order_by('student__first_name', 'student__last_name')
    # Ensure checklist exists
    checklist, _ = PreTripChecklist.objects.get_or_create(trip=trip)

    return render(request, 'departments/driver/trip_detail.html', {
        'trip': trip,
        'trip_students': trip_students,
        'checklist': checklist,
        'boarded_count': trip_students.filter(boarding_status='boarded').count(),
        'dropped_count': trip_students.filter(boarding_status='dropped').count(),
        'pending_count': trip_students.filter(boarding_status='pending').count(),
    })


@login_required
def trip_start(request, trip_id):
    """Mark trip as in_progress."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trip = get_object_or_404(Trip, id=trip_id, school=request.user.school, driver=request.user)
    trip.status = 'in_progress'
    trip.save(update_fields=['status'])
    messages.success(request, f'Trip started: {trip}')
    return redirect('trip_detail', trip_id=trip.id)


@login_required
def trip_complete(request, trip_id):
    """Mark trip as completed."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trip = get_object_or_404(Trip, id=trip_id, school=request.user.school, driver=request.user)
    trip.status = 'completed'
    trip.arrival_time = timezone.now().time()
    trip.save(update_fields=['status', 'arrival_time'])
    messages.success(request, f'Trip completed: {trip}')
    return redirect('trip_detail', trip_id=trip.id)


@login_required
def trip_student_mark(request, trip_id, student_id):
    """Mark a student as boarded / dropped / absent."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trip = get_object_or_404(Trip, id=trip_id, school=request.user.school, driver=request.user)
    ts = get_object_or_404(TripStudent, trip=trip, student_id=student_id)

    action = request.POST.get('action', '').strip()
    now = timezone.now()

    if action == 'boarded':
        ts.boarding_status = 'boarded'
        ts.boarded_at = now
    elif action == 'dropped':
        ts.boarding_status = 'dropped'
        ts.dropped_at = now
    elif action == 'absent':
        ts.boarding_status = 'absent'
    elif action == 'reset':
        ts.boarding_status = 'pending'
        ts.boarded_at = None
        ts.dropped_at = None

    ts.save()
    messages.success(request, f'{ts.student.full_name} → {ts.get_boarding_status_display()}')
    return redirect('trip_detail', trip_id=trip.id)


@login_required
def checklist_update(request, trip_id):
    """Update pre-trip checklist."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trip = get_object_or_404(Trip, id=trip_id, school=request.user.school, driver=request.user)
    checklist, _ = PreTripChecklist.objects.get_or_create(trip=trip)

    if request.method == 'POST':
        checklist.brakes_ok = 'brakes_ok' in request.POST
        checklist.tyres_ok = 'tyres_ok' in request.POST
        checklist.lights_ok = 'lights_ok' in request.POST
        checklist.mirrors_ok = 'mirrors_ok' in request.POST
        checklist.fuel_sufficient = 'fuel_sufficient' in request.POST
        checklist.first_aid_kit = 'first_aid_kit' in request.POST
        checklist.fire_extinguisher = 'fire_extinguisher' in request.POST
        checklist.seatbelts_ok = 'seatbelts_ok' in request.POST
        checklist.issues_found = request.POST.get('issues_found', '').strip()

        all_ok = all([
            checklist.brakes_ok, checklist.tyres_ok, checklist.lights_ok,
            checklist.mirrors_ok, checklist.fuel_sufficient,
            checklist.first_aid_kit, checklist.fire_extinguisher,
            checklist.seatbelts_ok,
        ])
        checklist.is_cleared = all_ok and not checklist.issues_found
        if checklist.is_cleared:
            checklist.cleared_at = timezone.now()
        checklist.save()

        messages.success(request, 'Checklist updated.')
        return redirect('trip_detail', trip_id=trip.id)

    return render(request, 'departments/driver/checklist_form.html', {
        'trip': trip,
        'checklist': checklist,
    })


@login_required
def fuel_log_list(request):
    """List all fuel logs for this driver."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    logs = FuelLog.objects.filter(
        school=request.user.school,
        driver=request.user,
    ).select_related('vehicle').order_by('-date', '-created_at')

    total = logs.aggregate(total=Sum('amount_kes'))['total'] or 0

    return render(request, 'departments/driver/fuel_list.html', {
        'logs': logs,
        'total': total,
    })


@login_required
def fuel_log_add(request):
    """Add a new fuel log entry."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    vehicles = Vehicle.objects.filter(school=school, is_active=True)

    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        date_val = request.POST.get('date')
        amount_kes = request.POST.get('amount_kes')
        litres = request.POST.get('litres') or None
        odometer = request.POST.get('odometer_reading') or None
        payment_method = request.POST.get('payment_method')
        payment_reference = request.POST.get('payment_reference', '').strip()
        station_name = request.POST.get('station_name', '').strip()
        notes = request.POST.get('notes', '').strip()
        receipt = request.FILES.get('receipt')

        errors = []
        if not vehicle_id:
            errors.append('Vehicle is required.')
        if not date_val:
            errors.append('Date is required.')
        if not amount_kes:
            errors.append('Amount is required.')
        if not payment_method:
            errors.append('Payment method is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/driver/fuel_form.html', {
                'vehicles': vehicles,
                'form_data': request.POST,
            })

        FuelLog.objects.create(
            school=school,
            vehicle_id=vehicle_id,
            driver=request.user,
            date=date_val,
            amount_kes=amount_kes,
            litres=litres,
            odometer_reading=odometer,
            payment_method=payment_method,
            payment_reference=payment_reference,
            station_name=station_name,
            notes=notes,
            receipt=receipt,
        )
        messages.success(request, 'Fuel log added.')
        return redirect('fuel_log_list')

    return render(request, 'departments/driver/fuel_form.html', {
        'vehicles': vehicles,
        'today': date.today(),
    })


@login_required
def trip_history(request):
    """All trips for this driver."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    trips = Trip.objects.filter(
        school=request.user.school,
        driver=request.user,
    ).select_related('route', 'vehicle').order_by('-date')

    return render(request, 'departments/driver/trip_history.html', {
        'trips': trips,
    })
    

# ============================================================
# TRIP MANIFEST — Print/PDF
# ============================================================

@login_required
def trip_manifest(request, trip_id):
    """Print-friendly trip manifest page."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Trip
    trip = get_object_or_404(
        Trip, id=trip_id,
        school=request.user.school,
        driver=request.user,
    )

    trip_students = trip.trip_students.select_related(
        'student'
    ).order_by('student__first_name', 'student__last_name')

    students_data = []
    for ts in trip_students:
        student = ts.student
        students_data.append({
            'ts': ts,
            'student': student,
            'parent_phone': student.guardian_phone or '',
            'parent_name': student.guardian_name or '',
            'stop_name': ts.stop_name,
        })

    return render(request, 'departments/driver/trip_manifest.html', {
        'trip': trip,
        'students_data': students_data,
        'school': request.user.school,
        'printed_at': timezone.now(),
    })


@login_required
def trip_manifest_pdf(request, trip_id):
    """PDF of trip manifest."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Trip
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    trip = get_object_or_404(
        Trip, id=trip_id,
        school=request.user.school,
        driver=request.user,
    )

    trip_students = trip.trip_students.select_related(
        'student'
    ).order_by('student__first_name', 'student__last_name')

    students_data = []
    for ts in trip_students:
        student = ts.student
        students_data.append({
            'ts': ts,
            'student': student,
            'parent_phone': student.guardian_phone or '',
            'parent_name': student.guardian_name or '',
            'stop_name': ts.stop_name,
        })

    html_string = render_to_string('departments/driver/trip_manifest_pdf.html', {
        'trip': trip,
        'students_data': students_data,
        'school': request.user.school,
        'printed_at': timezone.now(),
    })

    try:
        from weasyprint import HTML
        response = HttpResponse(content_type='application/pdf')
        filename = f"manifest_{trip.route.name.replace(' ', '_')}_{trip.date}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        return response
    except ImportError:
        messages.error(request, 'PDF generation not available.')
        return redirect('trip_detail', trip_id=trip.id)


@login_required
def my_students(request):
    """All students assigned to this driver."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import TripStudent
    from apps.students.models import Student

    student_ids = TripStudent.objects.filter(
        trip__driver=request.user,
        trip__school=request.user.school,
    ).values_list('student_id', flat=True).distinct()

    students = Student.objects.filter(
        id__in=student_ids, is_active=True
    ).order_by('first_name', 'last_name')

    students_data = []
    for student in students:
        students_data.append({
            'student': student,
            'parent_name': student.guardian_name or '',
            'parent_phone': student.guardian_phone or '',
        })

    return render(request, 'departments/driver/my_students.html', {
        'students_data': students_data,
        'total': len(students_data),
    })


@login_required
def my_students_pdf(request):
    """PDF of all students assigned to this driver."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import TripStudent
    from apps.students.models import Student
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    student_ids = TripStudent.objects.filter(
        trip__driver=request.user,
        trip__school=request.user.school,
    ).values_list('student_id', flat=True).distinct()

    students = Student.objects.filter(
        id__in=student_ids, is_active=True
    ).order_by('first_name', 'last_name')

    students_data = []
    for student in students:
        students_data.append({
            'student': student,
            'parent_name': student.guardian_name or '',
            'parent_phone': student.guardian_phone or '',
        })

    html_string = render_to_string('departments/driver/my_students_pdf.html', {
        'students_data': students_data,
        'school': request.user.school,
        'driver': request.user,
        'printed_at': timezone.now(),
    })

       # Use xhtml2pdf (pure Python, no native libs)
    from xhtml2pdf import pisa
    import io

    response = HttpResponse(content_type='application/pdf')
    filename = f"my_students_{request.user.get_full_name() or request.user.email}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    result = pisa.CreatePDF(
        src=io.StringIO(html_string),
        dest=response,
        encoding='utf-8',
    )

    if result.err:
        messages.error(request, f'PDF generation failed: {result.err}')
        return redirect('my_students')

    return response