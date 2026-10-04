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
    

# ============================================================
# REPORT PDF + PRINT
# ============================================================

def _reports_queryset(request):
    """Build filtered reports queryset for current user."""
    from .models import DepartmentReport
    school = request.user.school
    qs = DepartmentReport.objects.filter(school=school).select_related(
        'submitted_by', 'reviewed_by'
    ).order_by('-report_date', '-created_at')

    dept_filter = request.GET.get('department')
    if dept_filter:
        qs = qs.filter(department=dept_filter)

    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    return qs, dept_filter, status_filter


@login_required
def report_pdf(request, report_id):
    """Download a single report as PDF."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from .models import DepartmentReport
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    report = get_object_or_404(
        DepartmentReport, id=report_id, school=request.user.school
    )

    html_string = render_to_string('departments/report_pdf.html', {
        'report': report,
        'school': request.user.school,
        'printed_at': timezone.now(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"report_{report.department}_{report.report_date}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    result = pisa.CreatePDF(
        src=io.StringIO(html_string),
        dest=response,
        encoding='utf-8',
    )

    if result.err:
        messages.error(request, 'PDF generation failed.')
        return redirect('department_reports_inbox')

    return response


@login_required
def reports_bulk_pdf(request):
    """Download all filtered reports as one PDF."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    import io

    reports, dept_filter, status_filter = _reports_queryset(request)

    dept_label = 'All Departments'
    if dept_filter:
        from .models import DepartmentChoices
        dept_label = dict(DepartmentChoices.choices).get(dept_filter, dept_filter)

    html_string = render_to_string('departments/reports_bulk_pdf.html', {
        'reports': reports,
        'school': request.user.school,
        'printed_at': timezone.now(),
        'department_label': dept_label,
        'status_filter': status_filter,
        'total': reports.count(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f"reports_{dept_filter or 'all'}_{timezone.now().date()}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    result = pisa.CreatePDF(
        src=io.StringIO(html_string),
        dest=response,
        encoding='utf-8',
    )

    if result.err:
        messages.error(request, 'PDF generation failed.')
        return redirect('department_reports_inbox')

    return response


@login_required
def reports_print(request):
    """Print-friendly view of filtered reports."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    reports, dept_filter, status_filter = _reports_queryset(request)

    dept_label = 'All Departments'
    if dept_filter:
        from .models import DepartmentChoices
        dept_label = dict(DepartmentChoices.choices).get(dept_filter, dept_filter)

    return render(request, 'departments/reports_print.html', {
        'reports': reports,
        'school': request.user.school,
        'printed_at': timezone.now(),
        'department_label': dept_label,
        'status_filter': status_filter,
        'total': reports.count(),
    })
    

# ============================================================
# REPORT REVIEW (School Admin)
# ============================================================

@login_required
def department_report_review(request, report_id):
    """School Admin reviews a single department report."""
    if request.user.role not in ('school_admin', 'super_admin'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from .models import DepartmentReport

    report = get_object_or_404(
        DepartmentReport, id=report_id, school=request.user.school
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'mark_reviewed':
            report.status = 'reviewed'
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.admin_notes = request.POST.get('admin_notes', '').strip()
            report.save()
            messages.success(request, 'Report marked as reviewed.')

        elif action == 'mark_actioned':
            report.status = 'actioned'
            report.reviewed_by = request.user
            report.reviewed_at = timezone.now()
            report.admin_notes = request.POST.get('admin_notes', '').strip()
            report.save()
            messages.success(request, 'Report marked as actioned.')

        elif action == 'save':
            report.admin_notes = request.POST.get('admin_notes', '').strip()
            report.save()
            messages.success(request, 'Notes saved.')

        return redirect('department_report_review', report_id=report.id)

    return render(request, 'departments/report_review.html', {
        'report': report,
    })