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
    return request.user.role == 'school_admin'

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
    today_trips = Trip.objects.filter(school=school, date=today).select_related(
        'route', 'vehicle', 'driver'
    ).order_by('direction')

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