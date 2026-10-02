from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import DepartmentReport, DepartmentChoices


# Map role → department
ROLE_DEPARTMENT_MAP = {
    'driver': DepartmentChoices.TRANSPORT,
    'librarian': DepartmentChoices.LIBRARY,
    'lab_technician': DepartmentChoices.LAB,
    'nurse': DepartmentChoices.HEALTH,
    'chief_chef': DepartmentChoices.KITCHEN,
}


def _dashboard_data(request, department, extra_context=None):
    """Shared dashboard data builder for all 5 roles."""
    school = request.user.school
    my_reports = DepartmentReport.objects.filter(
        school=school, department=department
    ).order_by('-report_date', '-created_at')
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    context = {
        'department': department,
        'my_reports': my_reports[:10],
        'total_reports': my_reports.count(),
        'today_reports': my_reports.filter(report_date=today).count(),
        'week_reports': my_reports.filter(report_date__gte=week_ago).count(),
        'pending_reports': my_reports.filter(status='submitted').count(),
    }
    if extra_context:
        context.update(extra_context)
    return context


@login_required
def driver_dashboard(request):
    if request.user.role != 'driver':
        return redirect('dashboard_home')
    return render(request, 'departments/driver_dashboard.html',
                  _dashboard_data(request, DepartmentChoices.TRANSPORT))


@login_required
def librarian_dashboard(request):
    if request.user.role != 'librarian':
        return redirect('dashboard_home')
    return render(request, 'departments/librarian_dashboard.html',
                  _dashboard_data(request, DepartmentChoices.LIBRARY))


@login_required
def lab_technician_dashboard(request):
    if request.user.role != 'lab_technician':
        return redirect('dashboard_home')
    return render(request, 'departments/lab_dashboard.html',
                  _dashboard_data(request, DepartmentChoices.LAB))


@login_required
def nurse_dashboard(request):
    if request.user.role != 'nurse':
        return redirect('dashboard_home')
    return render(request, 'departments/nurse_dashboard.html',
                  _dashboard_data(request, DepartmentChoices.HEALTH))


@login_required
def chief_chef_dashboard(request):
    if request.user.role != 'chief_chef':
        return redirect('dashboard_home')
    return render(request, 'departments/chef_dashboard.html',
                  _dashboard_data(request, DepartmentChoices.KITCHEN))


@login_required
def department_report_create(request, department_code):
    """Shared report submission for all departments."""
    user = request.user
    allowed = ROLE_DEPARTMENT_MAP.get(user.role)
    
    if allowed != department_code and user.role not in ('school_admin', 'super_admin'):
        messages.error(request, 'You cannot submit reports for this department.')
        return redirect('dashboard_home')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        report_date = request.POST.get('report_date')
        priority = request.POST.get('priority', 'normal')
        attachment = request.FILES.get('attachment')
        
        if not title or not description or not report_date:
            messages.error(request, 'Please fill in all required fields.')
        else:
            DepartmentReport.objects.create(
                school=user.school,
                department=department_code,
                title=title,
                description=description,
                report_date=report_date,
                priority=priority,
                submitted_by=user,
                attachment=attachment,
            )
            messages.success(request, 'Report submitted successfully.')
            
            # Redirect based on role
            redirect_map = {
                'driver': 'driver_dashboard',
                'librarian': 'librarian_dashboard',
                'lab_technician': 'lab_technician_dashboard',
                'nurse': 'nurse_dashboard',
                'chief_chef': 'chief_chef_dashboard',
            }
            return redirect(redirect_map.get(user.role, 'dashboard_home'))
    
    return render(request, 'departments/report_form.html', {
        'department_code': department_code,
        'department_name': dict(DepartmentChoices.choices).get(department_code, department_code),
    })


@login_required
def department_reports_inbox(request):
    """School admin — see all department reports."""
    if request.user.role not in ('school_admin', 'super_admin'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')
    
    school = request.user.school
    reports = DepartmentReport.objects.filter(school=school).order_by('-report_date', '-created_at')
    
    dept_filter = request.GET.get('department')
    if dept_filter:
        reports = reports.filter(department=dept_filter)
    
    counts = {}
    for code, label in DepartmentChoices.choices:
        qs = DepartmentReport.objects.filter(school=school, department=code)
        counts[code] = {
            'label': label,
            'total': qs.count(),
            'pending': qs.filter(status='submitted').count(),
        }
    
    return render(request, 'departments/admin_inbox.html', {
        'reports': reports[:100],
        'counts': counts,
        'current_dept': dept_filter,
    })