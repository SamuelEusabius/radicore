"""
School Admin — Departments Hub
Manage transport, library, lab, health, kitchen for their school.
"""
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone


def _school_admin_required(request):
    """Only School Admin can access department pages. Super Admin is blocked."""
    return request.user.role == 'principal'

# ============================================================
# HUB — 5 department cards
# ============================================================

@login_required
def departments_hub(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    if not school:
        messages.error(request, 'No school linked to your account.')
        return redirect('dashboard_home')

    # Gather stats from each department (safe — uses try/except)
    stats = {}

    try:
        from apps.departments.models import Vehicle, Route, Trip, FuelLog, DepartmentReport
        today = date.today()

        stats['transport'] = {
            'vehicles': Vehicle.objects.filter(school=school, is_active=True).count(),
            'routes': Route.objects.filter(school=school, is_active=True).count(),
            'today_trips': Trip.objects.filter(school=school, date=today).count(),
            'fuel_30d': FuelLog.objects.filter(
                school=school, date__gte=today - timedelta(days=30)
            ).aggregate(t=Sum('amount_kes'))['t'] or 0,
            'pending_reports': DepartmentReport.objects.filter(
                school=school, department='transport', status='submitted'
            ).count(),
        }
    except Exception:
        stats['transport'] = {}

    try:
        from apps.departments.models import DepartmentReport
        stats['library'] = {
            'pending_reports': DepartmentReport.objects.filter(
                school=school, department='library', status='submitted'
            ).count(),
        }
    except Exception:
        stats['library'] = {}

    try:
        from apps.departments.models import DepartmentReport
        stats['lab'] = {
            'pending_reports': DepartmentReport.objects.filter(
                school=school, department='lab', status='submitted'
            ).count(),
        }
    except Exception:
        stats['lab'] = {}

    try:
        from apps.departments.models import DepartmentReport
        stats['health'] = {
            'pending_reports': DepartmentReport.objects.filter(
                school=school, department='health', status='submitted'
            ).count(),
        }
    except Exception:
        stats['health'] = {}

    try:
        from apps.departments.models import DepartmentReport
        stats['kitchen'] = {
            'pending_reports': DepartmentReport.objects.filter(
                school=school, department='kitchen', status='submitted'
            ).count(),
        }
    except Exception:
        stats['kitchen'] = {}

    # Total pending across all departments
    total_pending = sum(d.get('pending_reports', 0) for d in stats.values())

    return render(request, 'dashboard/departments/hub.html', {
        'stats': stats,
        'total_pending': total_pending,
    })


# ============================================================
# TRANSPORT — Full admin page
# ============================================================

@login_required
def departments_transport(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    school = request.user.school
    from apps.departments.models import Vehicle, Route, Trip, FuelLog, TripStudent

    today = date.today()

    vehicles = Vehicle.objects.filter(school=school).order_by('plate_number')
    routes = Route.objects.filter(school=school).order_by('name')
    today_trips = Trip.objects.filter(
        school=school,
        date__gte=today,
        date__lte=today + timedelta(days=30)
    ).select_related('route', 'vehicle', 'driver').order_by('date', 'direction')[:30]
    # Fuel totals
    thirty_days_ago = today - timedelta(days=30)
    fuel_total = FuelLog.objects.filter(
        school=school, date__gte=thirty_days_ago
    ).aggregate(t=Sum('amount_kes'))['t'] or 0

    # Recent fuel logs
    recent_fuel = FuelLog.objects.filter(school=school).select_related(
        'vehicle', 'driver'
    ).order_by('-date', '-created_at')[:10]

    return render(request, 'dashboard/departments/transport.html', {
        'vehicles': vehicles,
        'routes': routes,
        'today_trips': today_trips,
        'fuel_total_30d': fuel_total,
        'recent_fuel': recent_fuel,
        'vehicle_count': vehicles.count(),
        'route_count': routes.count(),
        'trip_count': today_trips.count(),
    })


# ============================================================
# LIBRARY — Stub
# ============================================================

@login_required
def departments_library(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')
    return render(request, 'dashboard/departments/library.html')


# ============================================================
# LAB — Stub
# ============================================================

@login_required
def departments_lab(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')
    return render(request, 'dashboard/departments/lab.html')


# ============================================================
# HEALTH — Stub
# ============================================================

@login_required
def departments_health(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')
    return render(request, 'dashboard/departments/health.html')


# ============================================================
# KITCHEN — Stub
# ============================================================

@login_required
def departments_kitchen(request):
    if not _school_admin_required(request):
        return redirect('dashboard_home')
    return render(request, 'dashboard/departments/kitchen.html')
  

# ============================================================
# TRANSPORT — VEHICLE CRUD
# ============================================================

@login_required
def transport_vehicle_form(request, vehicle_id=None):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Vehicle
    school = request.user.school

    vehicle = None
    if vehicle_id:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, school=school)

    if request.method == 'POST':
        plate = request.POST.get('plate_number', '').strip().upper()
        make = request.POST.get('make', '').strip()
        model = request.POST.get('model', '').strip()
        capacity = request.POST.get('capacity', '40').strip()
        notes = request.POST.get('notes', '').strip()
        is_active = 'is_active' in request.POST

        errors = []
        if not plate:
            errors.append('Plate number is required.')

        existing = Vehicle.objects.filter(school=school, plate_number=plate)
        if vehicle:
            existing = existing.exclude(id=vehicle.id)
        if existing.exists():
            errors.append(f'Vehicle "{plate}" already exists.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/departments/transport/vehicle_form.html', {
                'vehicle': vehicle,
                'form_data': request.POST,
            })

        if vehicle:
            vehicle.plate_number = plate
            vehicle.make = make
            vehicle.model = model
            vehicle.capacity = capacity or 40
            vehicle.notes = notes
            vehicle.is_active = is_active
            vehicle.save()
            messages.success(request, f'Vehicle "{plate}" updated.')
        else:
            Vehicle.objects.create(
                school=school, plate_number=plate, make=make, model=model,
                capacity=capacity or 40, notes=notes, is_active=is_active,
            )
            messages.success(request, f'Vehicle "{plate}" added.')

        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/vehicle_form.html', {
        'vehicle': vehicle,
    })


@login_required
def transport_vehicle_delete(request, vehicle_id):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Vehicle
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, school=request.user.school)

    if request.method == 'POST':
        name = vehicle.plate_number
        vehicle.delete()
        messages.success(request, f'Vehicle "{name}" deleted.')
        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/confirm_delete.html', {
        'object_name': vehicle.plate_number,
        'object_type': 'Vehicle',
        'cancel_url': 'departments_transport',
    })


# ============================================================
# TRANSPORT — ROUTE CRUD
# ============================================================

@login_required
def transport_route_form(request, route_id=None):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Route
    school = request.user.school

    route = None
    if route_id:
        route = get_object_or_404(Route, id=route_id, school=school)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        morning = request.POST.get('morning_departure') or None
        evening = request.POST.get('evening_departure') or None
        is_active = 'is_active' in request.POST

        errors = []
        if not name:
            errors.append('Route name is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/departments/transport/route_form.html', {
                'route': route,
                'form_data': request.POST,
            })

        if route:
            route.name = name
            route.description = description
            route.morning_departure = morning
            route.evening_departure = evening
            route.is_active = is_active
            route.save()
            messages.success(request, f'Route "{name}" updated.')
        else:
            Route.objects.create(
                school=school, name=name, description=description,
                morning_departure=morning, evening_departure=evening,
                is_active=is_active,
            )
            messages.success(request, f'Route "{name}" added.')

        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/route_form.html', {
        'route': route,
    })


@login_required
def transport_route_delete(request, route_id):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Route
    route = get_object_or_404(Route, id=route_id, school=request.user.school)

    if request.method == 'POST':
        name = route.name
        route.delete()
        messages.success(request, f'Route "{name}" deleted.')
        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/confirm_delete.html', {
        'object_name': route.name,
        'object_type': 'Route',
        'cancel_url': 'departments_transport',
    })


# ============================================================
# TRANSPORT — TRIP CRUD
# ============================================================

@login_required
def transport_trip_form(request, trip_id=None):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Trip, Route, Vehicle
    from apps.accounts.models import User
    from datetime import date as dt

    school = request.user.school

    trip = None
    if trip_id:
        trip = get_object_or_404(Trip, id=trip_id, school=school)

    routes = Route.objects.filter(school=school, is_active=True).order_by('name')
    vehicles = Vehicle.objects.filter(school=school, is_active=True).order_by('plate_number')
    drivers = User.objects.filter(school=school, role='driver', is_active=True).order_by('first_name')

    if request.method == 'POST':
        route_id = request.POST.get('route', '').strip()
        vehicle_id = request.POST.get('vehicle', '').strip() or None
        driver_id = request.POST.get('driver', '').strip() or None
        date_val = request.POST.get('date', '').strip()
        direction = request.POST.get('direction', '').strip()
        departure = request.POST.get('departure_time') or None
        status = request.POST.get('status', 'scheduled').strip()
        notes = request.POST.get('notes', '').strip()

        errors = []
        if not route_id:
            errors.append('Route is required.')
        if not date_val:
            errors.append('Date is required.')
        if not direction:
            errors.append('Direction is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/departments/transport/trip_form.html', {
                'trip': trip, 'routes': routes, 'vehicles': vehicles,
                'drivers': drivers, 'form_data': request.POST,
            })

        if trip:
            trip.route_id = route_id
            trip.vehicle_id = vehicle_id
            trip.driver_id = driver_id
            trip.date = date_val
            trip.direction = direction
            trip.departure_time = departure
            trip.status = status
            trip.notes = notes
            trip.save()
            messages.success(request, 'Trip updated.')
        else:
            Trip.objects.create(
                school=school, route_id=route_id, vehicle_id=vehicle_id,
                driver_id=driver_id, date=date_val, direction=direction,
                departure_time=departure, status=status, notes=notes,
            )
            messages.success(request, 'Trip scheduled.')

        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/trip_form.html', {
        'trip': trip, 'routes': routes, 'vehicles': vehicles,
        'drivers': drivers, 'today': dt.today(),
    })


@login_required
def transport_trip_delete(request, trip_id):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Trip
    trip = get_object_or_404(Trip, id=trip_id, school=request.user.school)

    if request.method == 'POST':
        info = f'{trip.route.name} - {trip.date}'
        trip.delete()
        messages.success(request, f'Trip "{info}" deleted.')
        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/confirm_delete.html', {
        'object_name': f'{trip.route.name} · {trip.date} · {trip.get_direction_display()}',
        'object_type': 'Trip',
        'cancel_url': 'departments_transport',
    })


# ============================================================
# TRANSPORT — FUEL LOG CRUD
# ============================================================

@login_required
def transport_fuel_form(request, fuel_id=None):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import FuelLog, Vehicle
    from apps.accounts.models import User
    from datetime import date as dt

    school = request.user.school

    fuel = None
    if fuel_id:
        fuel = get_object_or_404(FuelLog, id=fuel_id, school=school)

    vehicles = Vehicle.objects.filter(school=school, is_active=True).order_by('plate_number')
    drivers = User.objects.filter(school=school, role='driver', is_active=True).order_by('first_name')

    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle', '').strip()
        driver_id = request.POST.get('driver', '').strip() or None
        date_val = request.POST.get('date', '').strip()
        amount = request.POST.get('amount_kes', '').strip()
        litres = request.POST.get('litres') or None
        odometer = request.POST.get('odometer_reading') or None
        payment_method = request.POST.get('payment_method', '').strip()
        reference = request.POST.get('payment_reference', '').strip()
        station = request.POST.get('station_name', '').strip()
        notes = request.POST.get('notes', '').strip()
        receipt = request.FILES.get('receipt')

        errors = []
        if not vehicle_id:
            errors.append('Vehicle is required.')
        if not date_val:
            errors.append('Date is required.')
        if not amount:
            errors.append('Amount is required.')
        if not payment_method:
            errors.append('Payment method is required.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/departments/transport/fuel_form.html', {
                'fuel': fuel, 'vehicles': vehicles, 'drivers': drivers,
                'today': dt.today(), 'form_data': request.POST,
            })

        if fuel:
            fuel.vehicle_id = vehicle_id
            fuel.driver_id = driver_id
            fuel.date = date_val
            fuel.amount_kes = amount
            fuel.litres = litres
            fuel.odometer_reading = odometer
            fuel.payment_method = payment_method
            fuel.payment_reference = reference
            fuel.station_name = station
            fuel.notes = notes
            if receipt:
                fuel.receipt = receipt
            fuel.save()
            messages.success(request, 'Fuel log updated.')
        else:
            FuelLog.objects.create(
                school=school, vehicle_id=vehicle_id, driver_id=driver_id,
                date=date_val, amount_kes=amount, litres=litres,
                odometer_reading=odometer, payment_method=payment_method,
                payment_reference=reference, station_name=station,
                notes=notes, receipt=receipt,
            )
            messages.success(request, 'Fuel log added.')

        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/fuel_form.html', {
        'fuel': fuel, 'vehicles': vehicles, 'drivers': drivers,
        'today': dt.today(),
    })


@login_required
def transport_fuel_delete(request, fuel_id):
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import FuelLog
    fuel = get_object_or_404(FuelLog, id=fuel_id, school=request.user.school)

    if request.method == 'POST':
        info = f'{fuel.vehicle.plate_number} - KES {fuel.amount_kes}'
        fuel.delete()
        messages.success(request, f'Fuel log "{info}" deleted.')
        return redirect('departments_transport')

    return render(request, 'dashboard/departments/transport/confirm_delete.html', {
        'object_name': f'{fuel.vehicle.plate_number} · KES {fuel.amount_kes} · {fuel.date}',
        'object_type': 'Fuel Log',
        'cancel_url': 'departments_transport',
    })
    

# ============================================================
# TRANSPORT — TRIP STUDENT ASSIGNMENT
# ============================================================

@login_required
def transport_trip_students(request, trip_id):
    """Manage which students are assigned to a trip."""
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Trip, TripStudent
    from apps.students.models import Student

    school = request.user.school
    trip = get_object_or_404(Trip, id=trip_id, school=school)

    # Currently assigned student IDs
    assigned_ids = set(
        TripStudent.objects.filter(trip=trip).values_list('student_id', flat=True)
    )

    # All active students in this school
    all_students = Student.objects.filter(
        school=school, is_active=True
    ).order_by('class_level', 'first_name', 'last_name')

    # Build rows
    student_rows = []
    for s in all_students:
        existing = TripStudent.objects.filter(trip=trip, student=s).first()
        student_rows.append({
            'student': s,
            'is_assigned': s.id in assigned_ids,
            'stop_name': existing.stop_name if existing else '',
        })

    if request.method == 'POST':
        selected_ids = set(
            int(x) for x in request.POST.getlist('students') if x.isdigit()
        )

        # Remove students no longer selected
        TripStudent.objects.filter(trip=trip).exclude(
            student_id__in=selected_ids
        ).delete()

        # Add new students
        for sid in selected_ids:
            if sid not in assigned_ids:
                # Find stop name for this student if provided
                stop_name = request.POST.get(f'stop_{sid}', '').strip()
                TripStudent.objects.create(
                    trip=trip,
                    student_id=sid,
                    boarding_status='pending',
                    stop_name=stop_name,
                )
            else:
                # Update stop name for existing
                stop_name = request.POST.get(f'stop_{sid}', '').strip()
                TripStudent.objects.filter(
                    trip=trip, student_id=sid
                ).update(stop_name=stop_name)

        messages.success(
            request,
            f'Trip roster updated: {len(selected_ids)} students assigned.'
        )
        return redirect('transport_trip_students', trip_id=trip.id)

    return render(request, 'dashboard/departments/transport/trip_students.html', {
        'trip': trip,
        'student_rows': student_rows,
        'assigned_count': len(assigned_ids),
        'total_students': len(student_rows),
    })


@login_required
def transport_trip_auto_assign(request, trip_id):
    """Quick-add: assign ALL students in a specific class to this trip."""
    if not _school_admin_required(request):
        return redirect('dashboard_home')

    from apps.departments.models import Trip, TripStudent
    from apps.students.models import Student

    school = request.user.school
    trip = get_object_or_404(Trip, id=trip_id, school=school)

    if request.method == 'POST':
        class_level = request.POST.get('class_level', '').strip()
        if not class_level:
            messages.error(request, 'Please select a class.')
            return redirect('transport_trip_students', trip_id=trip.id)

        students = Student.objects.filter(
            school=school, is_active=True, class_level=class_level
        )

        added = 0
        for s in students:
            _, created = TripStudent.objects.get_or_create(
                trip=trip,
                student=s,
                defaults={'boarding_status': 'pending'},
            )
            if created:
                added += 1

        messages.success(
            request,
            f'Added {added} students from {class_level} to this trip.'
        )

    return redirect('transport_trip_students', trip_id=trip.id)