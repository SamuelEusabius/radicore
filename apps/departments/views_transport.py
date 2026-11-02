from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.views.decorators.http import require_POST

from .models import (
    Trip, TripStudent, Route, Vehicle, FuelLog, PreTripChecklist,
    DepartmentReport, DepartmentChoices,
)


def _driver_required(request):
    """Return True if user is a driver or admin."""
    return request.user.role in ('driver', 'principal', 'super_admin')


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
        'student'
    ).order_by('student__first_name', 'student__last_name')
    checklist, _ = PreTripChecklist.objects.get_or_create(trip=trip)

    return render(request, 'departments/driver/trip_detail.html', {
        'trip': trip,
        'trip_students': trip_students,
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
        'today': timezone.localdate()
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

# ==========================================================
# DRIVER PDF REPORTS
# ==========================================================

@login_required
def driver_trip_history_pdf(request):
    """PDF of the driver's trip history for a selectable period."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    period = request.GET.get('period', 'month').strip()

    # Calculate date range
    today = timezone.localdate()
    if period == 'today':
        start_date = today
        period_label = 'Today'
    elif period == 'week':
        start_date = today - timedelta(days=7)
        period_label = 'Last 7 Days'
    elif period == 'month':
        start_date = today.replace(day=1)
        period_label = 'This Month'
    elif period == 'term':
        # Assume term is ~3 months
        start_date = today - timedelta(days=90)
        period_label = 'Last 90 Days (Term)'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        period_label = 'This Year'
    else:
        start_date = today.replace(day=1)
        period_label = 'This Month'

    trips = Trip.objects.filter(
        school=school,
        driver=request.user,
        date__gte=start_date,
        date__lte=today,
    ).select_related('route', 'vehicle').order_by('-date', 'direction')

    # Aggregate fuel
    fuel_qs = FuelLog.objects.filter(
        school=school,
        driver=request.user,
        date__gte=start_date,
    )
    fuel_total = fuel_qs.aggregate(total=Sum('amount_kes'))['total'] or 0
    fuel_litres = fuel_qs.aggregate(total=Sum('litres'))['total'] or 0

    from apps.core.pdf_utils import html_to_pdf_response, build_pdf_context
    from django.template.loader import render_to_string

    context = build_pdf_context(
        school, request.user,
        driver=request.user,
        trips=trips,
        period_label=period_label,
        period_start=start_date,
        period_end=today,
        fuel_total=fuel_total,
        fuel_litres=fuel_litres,
        trip_count=trips.count(),
    )

    html_string = render_to_string('pdf/driver_trip_history.html', context)
    return html_to_pdf_response(
        html_string,
        f'trip_history_{request.user.id}_{period}.pdf',
    )


@login_required
def driver_fuel_report_pdf(request):
    """PDF of the driver's fuel usage and KM covered for a period."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    period = request.GET.get('period', 'month').strip()

    today = timezone.localdate()
    if period == 'today':
        start_date = today
        period_label = 'Today'
    elif period == 'week':
        start_date = today - timedelta(days=7)
        period_label = 'Last 7 Days'
    elif period == 'month':
        start_date = today.replace(day=1)
        period_label = 'This Month'
    elif period == 'term':
        start_date = today - timedelta(days=90)
        period_label = 'Last 90 Days (Term)'
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
        period_label = 'This Year'
    else:
        start_date = today.replace(day=1)
        period_label = 'This Month'

    fuel_logs = FuelLog.objects.filter(
        school=school,
        driver=request.user,
        date__gte=start_date,
        date__lte=today,
    ).select_related('vehicle').order_by('-date')

    fuel_total = fuel_logs.aggregate(total=Sum('amount_kes'))['total'] or 0
    fuel_litres = fuel_logs.aggregate(total=Sum('litres'))['total'] or 0

    # Total KM from trips
    trips = Trip.objects.filter(
        school=school,
        driver=request.user,
        date__gte=start_date,
        date__lte=today,
        status='completed',
    )
    total_km = trips.aggregate(total=Sum('km_covered'))['total'] or 0 if hasattr(Trip, 'km_covered') else 0

    cost_per_km = round(float(fuel_total) / total_km, 2) if total_km > 0 else 0

    from apps.core.pdf_utils import html_to_pdf_response, build_pdf_context
    from django.template.loader import render_to_string

    context = build_pdf_context(
        school, request.user,
        driver=request.user,
        fuel_logs=fuel_logs,
        period_label=period_label,
        period_start=start_date,
        period_end=today,
        fuel_total=fuel_total,
        fuel_litres=fuel_litres,
        total_km=total_km,
        cost_per_km=cost_per_km,
        trip_count=trips.count(),
    )

    html_string = render_to_string('pdf/driver_fuel_report.html', context)
    return html_to_pdf_response(
        html_string,
        f'fuel_report_{request.user.id}_{period}.pdf',
    )
    
@login_required
def admin_transport_dashboard(request):
    """Read-only transport overview for the Principal/Admin."""
    if request.user.role not in ('principal', 'deputy_admin', 'super_admin'):
        return redirect('dashboard_home')

    from .models import Vehicle, Route, Trip, FuelLog, DepartmentReport
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum

    school = request.user.school
    thirty_days_ago = timezone.now().date() - timedelta(days=30)

    vehicles = Vehicle.objects.filter(school=school, is_active=True)
    routes = Route.objects.filter(school=school, is_active=True)
    
    upcoming_trips = Trip.objects.filter(
        school=school, date__gte=timezone.now().date()
    ).order_by('date', 'departure_time')

    fuel_spend = FuelLog.objects.filter(
        school=school, date__gte=thirty_days_ago
    ).aggregate(total=Sum('amount_kes'))['total'] or 0

    # Fetch driver reports
    driver_reports = DepartmentReport.objects.filter(
        school=school, department='transport'
    ).order_by('-created_at')[:10]

    return render(request, 'dashboard/departments/transport.html', {
        'vehicles': vehicles,
        'vehicle_count': vehicles.count(),
        'route_count': routes.count(),
        'upcoming_trips': upcoming_trips,
        'upcoming_trips_count': upcoming_trips.count(),
        'fuel_spend_30d': fuel_spend,
        'driver_reports': driver_reports,
    })
    
    # ============================================================
# VEHICLE CRUD (Driver)
# ============================================================

@login_required
def vehicle_list(request):
    """Driver sees all vehicles in their school + Add button."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Vehicle

    school = request.user.school
    vehicles = Vehicle.objects.filter(school=school).order_by('-is_active', 'plate_number')

    return render(request, 'departments/driver/vehicle_list.html', {
        'vehicles': vehicles,
    })


@login_required
def vehicle_form(request, vehicle_id=None):
    """Create or edit a vehicle."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Vehicle

    school = request.user.school
    vehicle = None
    if vehicle_id:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, school=school)

    if request.method == 'POST':
        plate = request.POST.get('plate_number', '').strip().upper()
        make = request.POST.get('make', '').strip()
        model_name = request.POST.get('model', '').strip()
        capacity = request.POST.get('capacity', '0').strip()
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not plate:
            errors.append('Plate number is required.')

        # Check for duplicate plate in same school
        existing = Vehicle.objects.filter(school=school, plate_number=plate)
        if vehicle:
            existing = existing.exclude(id=vehicle.id)
        if existing.exists():
            errors.append(f'A vehicle with plate "{plate}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/driver/vehicle_form.html', {
                'vehicle': vehicle,
                'form_data': request.POST,
            })

        if vehicle:
            vehicle.plate_number = plate
            vehicle.make = make
            vehicle.model = model_name
            vehicle.capacity = int(capacity or 40)
            vehicle.is_active = is_active
            vehicle.save()
            messages.success(request, f'Vehicle {plate} updated.')
        else:
            Vehicle.objects.create(
                school=school,
                plate_number=plate,
                make=make,
                model=model_name,
                capacity=int(capacity or 40),
                is_active=is_active,
            )
            messages.success(request, f'Vehicle {plate} added.')

        return redirect('vehicle_list')

    return render(request, 'departments/driver/vehicle_form.html', {
        'vehicle': vehicle,
        'form_data': {},
    })


@login_required
@require_POST
def vehicle_delete(request, vehicle_id):
    """Delete a vehicle if it has no scheduled trips."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Vehicle, Trip

    school = request.user.school
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, school=school)

    active_trips = Trip.objects.filter(
        vehicle=vehicle,
        status__in=['scheduled', 'in_progress']
    ).count()

    if active_trips > 0:
        messages.error(request, f'Cannot delete {vehicle.plate_number}: it has {active_trips} active trip(s).')
        return redirect('vehicle_list')

    plate = vehicle.plate_number
    vehicle.delete()
    messages.success(request, f'Vehicle {plate} deleted.')
    return redirect('vehicle_list')


# ============================================================
# TRIP CRUD (Driver)
# ============================================================

@login_required
def trip_list(request):
    """Driver sees their assigned trips."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Trip

    school = request.user.school
    trips = (
        Trip.objects
        .filter(school=school, driver=request.user)
        .select_related('route', 'vehicle')
        .order_by('-date', '-departure_time')
    )

    return render(request, 'departments/driver/trip_list.html', {
        'trips': trips,
    })


@login_required
def trip_form(request, trip_id=None):
    """Create or edit a trip."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Trip, Route, Vehicle
    from django.utils import timezone

    school = request.user.school
    trip = None
    if trip_id:
        trip = get_object_or_404(Trip, id=trip_id, school=school, driver=request.user)

    routes = Route.objects.filter(school=school, is_active=True).order_by('name')
    vehicles = Vehicle.objects.filter(school=school, is_active=True).order_by('plate_number')

    if request.method == 'POST':
        route_id = request.POST.get('route')
        vehicle_id = request.POST.get('vehicle') or None
        date = request.POST.get('date')
        direction = request.POST.get('direction')
        departure_time = request.POST.get('departure_time') or None
        arrival_time = request.POST.get('arrival_time') or None
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not route_id:
            errors.append('Route is required.')
        if not date:
            errors.append('Date is required.')
        if not direction:
            errors.append('Direction is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/driver/trip_form.html', {
                'trip': trip,
                'routes': routes,
                'vehicles': vehicles,
                'form_data': request.POST,
            })

        route = get_object_or_404(Route, id=route_id, school=school)
        vehicle = Vehicle.objects.filter(id=vehicle_id, school=school).first() if vehicle_id else None

        if trip:
            trip.route = route
            trip.vehicle = vehicle
            trip.date = date
            trip.direction = direction
            trip.departure_time = departure_time
            trip.arrival_time = arrival_time
            trip.notes = notes
            trip.save()
            messages.success(request, 'Trip updated.')
            return redirect('trip_detail', trip_id=trip.id)
        else:
            trip = Trip.objects.create(
                school=school,
                route=route,
                vehicle=vehicle,
                driver=request.user,
                date=date,
                direction=direction,
                departure_time=departure_time,
                arrival_time=arrival_time,
                notes=notes,
                status='scheduled',
            )
            messages.success(request, 'Trip scheduled. Now add students to the manifest.')
            return redirect('trip_assign_students', trip_id=trip.id)

    return render(request, 'departments/driver/trip_form.html', {
        'trip': trip,
        'routes': routes,
        'vehicles': vehicles,
        'form_data': {},   
    })


@login_required
def trip_assign_students(request, trip_id):
    """Assign students to a trip (searchable + filterable)."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Trip, TripStudent
    from apps.students.models import Student
    from apps.academics.models import ClassLevel

    school = request.user.school
    trip = get_object_or_404(Trip, id=trip_id, school=school, driver=request.user)

    # Only boarding students typically take transport
    all_students = Student.objects.filter(school=school, is_active=True).order_by('first_name', 'last_name')
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # Already on this trip
    assigned_ids = set(
        TripStudent.objects.filter(trip=trip).values_list('student_id', flat=True)
    )

    if request.method == 'POST':
        selected_ids = request.POST.getlist('students')
        selected_ids = set(int(sid) for sid in selected_ids if str(sid).isdigit())

        # Remove anyone unchecked
        TripStudent.objects.filter(trip=trip).exclude(student_id__in=selected_ids).delete()

        # Add new ones
        existing_assigned = set(
            TripStudent.objects.filter(trip=trip).values_list('student_id', flat=True)
        )
        for sid in selected_ids - existing_assigned:
            if all_students.filter(id=sid).exists():
                TripStudent.objects.create(trip=trip, student_id=sid)

        messages.success(request, f'Updated manifest for {trip.route.name} on {trip.date}.')
        return redirect('trip_detail', trip_id=trip.id)

    return render(request, 'departments/driver/trip_assign_students.html', {
        'trip': trip,
        'students': all_students,
        'classes': classes,
        'assigned_ids': assigned_ids,
    })
    
@login_required
def route_form(request, route_id=None):
    """Create or edit a route."""
    if not _driver_required(request):
        return redirect('dashboard_home')

    from .models import Route

    school = request.user.school
    route = None
    if route_id:
        route = get_object_or_404(Route, id=route_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        morning_departure = request.POST.get('morning_departure') or None
        evening_departure = request.POST.get('evening_departure') or None
        is_active = request.POST.get('is_active') == 'on'

        errors = []
        if not name:
            errors.append('Route name is required.')

        # Check for duplicate name
        existing = Route.objects.filter(school=school, name=name)
        if route:
            existing = existing.exclude(id=route.id)
        if existing.exists():
            errors.append(f'A route named "{name}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'departments/driver/route_form.html', {
                'route': route,
                'form_data': request.POST,
            })

        if route:
            route.name = name
            route.description = description
            route.morning_departure = morning_departure
            route.evening_departure = evening_departure
            route.is_active = is_active
            route.save()
            messages.success(request, f'Route "{name}" updated.')
        else:
            Route.objects.create(
                school=school,
                name=name,
                description=description,
                morning_departure=morning_departure,
                evening_departure=evening_departure,
                is_active=is_active,
            )
            messages.success(request, f'Route "{name}" created.')

        return redirect('trip_create')

    return render(request, 'departments/driver/route_form.html', {
        'route': route,
        'form_data': {},
    })