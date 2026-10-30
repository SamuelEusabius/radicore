"""
Security / Chief Security Officer (CSO) views.

All views are gated with @role_required('security_officer', ...) and
tenant-scoped via request.school (from SchoolTenantMiddleware).
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.students.models import Student

from .forms import (
    VisitorCheckInForm, VisitorCheckOutForm, GatePassIssueForm,
    IncidentForm, LostItemForm, ClaimLostItemForm, SecurityShiftForm,
)
from .models import (
    Visitor, GatePass, Incident, LostItem, SecurityShift,
)
from .services import notify_host_of_visitor, notify_secretary_of_official


# ==========================================================
# Helpers
# ==========================================================

CSO_ROLES = ('security_officer', 'principal', 'deputy_admin', 'secretary')


def _school(request):
    school = getattr(request, 'school', None)
    if not school and request.user.is_authenticated:
        school = getattr(request.user, 'school', None)
    if not school:
        raise PermissionError("No school attached to this request.")
    return school


# ==========================================================
# Dashboard
# ==========================================================

@role_required(*CSO_ROLES)
def cso_dashboard(request):
    """CSO dashboard — quick overview of today's gate activity."""
    school = _school(request)
    today = timezone.localdate()

    visitors_today = Visitor.objects.filter(
        school=school, created_at__date=today
    ).select_related('host_user')

    # Anyone who has registered but not yet exited/cancelled is "on premises"
    on_premises = Visitor.objects.filter(
        school=school,
        status__in=[
            Visitor.Status.REGISTERED,
            Visitor.Status.IN_MEETING,
            Visitor.Status.SIGNED_OUT,
        ]
    ).select_related('host_user')

    # Active gate passes (not yet used or cancelled)
    active_passes = GatePass.objects.filter(
        school=school,
        status__in=[
            GatePass.Status.PENDING,
            GatePass.Status.ACTIVE,
            GatePass.Status.SIGNED,
        ]
    ).select_related('visitor')

    recent_incidents = Incident.objects.filter(
        school=school
    ).order_by('-created_at')[:5]

    return render(request, 'dashboards/cso/dashboard.html', {
        'school': school,
        'today': today,
        'visitors_today': visitors_today,
        'visitors_today_count': visitors_today.count(),
        'on_premises': on_premises,
        'on_premises_count': on_premises.count(),
        'active_passes': active_passes,
        'active_passes_count': active_passes.count(),
        'recent_incidents': recent_incidents,
    })
    
# ==========================================================
# Visitors — register, list, detail, check out
# ==========================================================

@role_required(*CSO_ROLES)
def visitor_list(request):
    school = _school(request)
    qs = Visitor.objects.filter(school=school).select_related(
        'host_user', 'registered_by', 'logged_out_by',
    )

    # Filters
    status = request.GET.get('status', '').strip()
    vtype = request.GET.get('type', '').strip()
    purpose = request.GET.get('purpose', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    search = request.GET.get('q', '').strip()

    if status == 'in':
        qs = qs.filter(time_out__isnull=True)
    elif status == 'out':
        qs = qs.filter(time_out__isnull=False)
    elif status:
        qs = qs.filter(status=status)

    if vtype:
        qs = qs.filter(visit_type=vtype)
    if purpose:
        qs = qs.filter(purpose=purpose)
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(organisation__icontains=search)
            | Q(host_name__icontains=search)
        )
    if date_from:
        qs = qs.filter(time_in__date__gte=date_from)
    if date_to:
        qs = qs.filter(time_in__date__lte=date_to)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'visitors': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'status': status,
        'vtype': vtype,
        'purpose': purpose,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'purpose_choices': Visitor.Purpose.choices,
    }
    return render(request, 'dashboards/cso/visitor_list.html', context)


@role_required(*CSO_ROLES)
def visitor_check_in(request):
    """CSO registers a visitor at the gate + auto-issues a gate pass."""
    school = _school(request)

    if request.method == 'POST':
        form = VisitorCheckInForm(request.POST, school=school)
        if form.is_valid():
            visitor = form.save(commit=False)
            visitor.school = school
            visitor.registered_by = request.user
            visitor.status = Visitor.Status.REGISTERED
            visitor.time_in = timezone.now()
            visitor.save()

            # Auto-issue gate pass
            pass_type = (
                GatePass.PassType.OFFICIAL
                if visitor.visit_type == Visitor.VisitType.OFFICIAL
                else GatePass.PassType.STANDARD
            )
            
            # --- GENERATE CUSTOM PASS NUMBER ---
            # Get the school initials (e.g. NAIROBI SCHOOL -> NS)
            school_prefix = "".join([word[0].upper() for word in school.name.split()])
            # Count existing passes to get the next number
            count = GatePass.objects.filter(school=school).count() + 1
            pass_number = f"GP-{school_prefix}-{count:04d}"

            gate_pass = GatePass.objects.create(
                school=school,
                visitor=visitor,
                pass_number=pass_number,
                pass_type=pass_type,
                destination=visitor.host_display,
                valid_from=timezone.now(),
                issued_by=request.user,
                status=GatePass.Status.ACTIVE,
            )

            # Notify host
            try:
                notify_host_of_visitor(visitor)
            except Exception:
                pass

            # Notify secretary for official visitors
            if visitor.is_official:
                try:
                    notify_secretary_of_official(visitor)
                except Exception:
                    pass
                messages.info(
                    request,
                    f"Official visitor. Secretary notified. Pass {gate_pass.pass_number} issued."
                )
            else:
                messages.success(
                    request,
                    f"{visitor.full_name} checked in. Pass {gate_pass.pass_number} issued."
                )

            return redirect('cso_visitor_detail', pk=visitor.pk)
    else:
        form = VisitorCheckInForm(school=school)

    return render(request, 'dashboards/cso/visitor_form.html', {
        'school': school,
        'form': form,
        'mode': 'check_in',
    })

@role_required(*CSO_ROLES)
def visitor_detail(request, pk):
    school = _school(request)
    visitor = get_object_or_404(
        Visitor.objects.select_related(
            'host_user', 'registered_by', 'logged_out_by',
            'official_pass_issued_by', 'admin_signed_by',
            'admin_confirmed_by_secretary',
        ),
        pk=pk, school=school,
    )
    gate_pass = getattr(visitor, 'gate_pass', None)

    return render(request, 'dashboards/cso/visitor_detail.html', {
        'school': school,
        'visitor': visitor,
        'gate_pass': gate_pass,
    })


@role_required(*CSO_ROLES)
def visitor_check_out(request, pk):
    """Log out a visitor at the gate."""
    school = _school(request)
    visitor = get_object_or_404(Visitor, pk=pk, school=school)

    if visitor.time_out:
        messages.warning(request, f"{visitor.full_name} is already checked out.")
        return redirect('cso_visitor_detail', pk=visitor.pk)

    if request.method == 'POST':
        form = VisitorCheckOutForm(request.POST)
        if form.is_valid():
            visitor.time_out = timezone.now()
            visitor.logged_out_by = request.user
            visitor.status = Visitor.Status.EXITED
            visitor.save()

            # Mark gate pass used
            gp = getattr(visitor, 'gate_pass', None)
            if gp and gp.status != GatePass.Status.USED:
                gp.status = GatePass.Status.USED
                gp.save(update_fields=['status', 'updated_at'])

            messages.success(request, f"{visitor.full_name} checked out.")
            return redirect('cso_visitor_list')
    else:
        form = VisitorCheckOutForm()

    return render(request, 'dashboards/cso/visitor_checkout.html', {
        'school': school,
        'visitor': visitor,
        'form': form,
    })


# ==========================================================
# Gate Passes
# ==========================================================

@role_required(*CSO_ROLES)
def gate_pass_list(request):
    school = _school(request)
    qs = GatePass.objects.filter(school=school).select_related(
        'visitor', 'issued_by', 'signed_by_user',
    )
    status = request.GET.get('status', '').strip()
    ptype = request.GET.get('type', '').strip()
    if status:
        qs = qs.filter(status=status)
    if ptype:
        qs = qs.filter(pass_type=ptype)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/cso/gate_pass_list.html', {
        'school': school,
        'passes': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'status': status,
        'ptype': ptype,
    })


@role_required(*CSO_ROLES)
def gate_pass_detail(request, pk):
    school = _school(request)
    gate_pass = get_object_or_404(
        GatePass.objects.select_related(
            'visitor', 'issued_by', 'signed_by_user', 'visitor__host_user',
        ),
        pk=pk, school=school,
    )
    return render(request, 'dashboards/cso/gate_pass_detail.html', {
        'school': school,
        'gate_pass': gate_pass,
        'visitor': gate_pass.visitor,
    })


@role_required(*CSO_ROLES)
def gate_pass_issue(request, visitor_id):
    """Issue a gate pass to a visitor (used when pass missing)."""
    school = _school(request)
    visitor = get_object_or_404(Visitor, pk=visitor_id, school=school)

    if hasattr(visitor, 'gate_pass'):
        messages.warning(request, "This visitor already has a gate pass.")
        return redirect('cso_gate_pass_detail', pk=visitor.gate_pass.pk)

    if request.method == 'POST':
        form = GatePassIssueForm(request.POST)
        if form.is_valid():
            gp = form.save(commit=False)
            gp.school = school
            gp.visitor = visitor
            gp.issued_by = request.user
            gp.status = GatePass.Status.ACTIVE
            gp.save()
            messages.success(request, f"Gate pass {gp.pass_number} issued.")
            return redirect('cso_gate_pass_detail', pk=gp.pk)
    else:
        form = GatePassIssueForm(initial={
            'pass_type': 'official' if visitor.is_official else 'standard',
            'destination': visitor.host_display,
            'valid_from': timezone.now(),
        })

    return render(request, 'dashboards/cso/gate_pass_form.html', {
        'school': school,
        'form': form,
        'visitor': visitor,
    })


@login_required
def gate_pass_print(request, pk):
    from django.template.loader import render_to_string
    from apps.core.pdf_utils import html_to_pdf_response
    from .models import GatePass
    
    gate_pass = get_object_or_404(GatePass, pk=pk, school=request.user.school)
    
    html_string = render_to_string('pdf/gate_pass.html', {
        'pass': gate_pass,
        'school': request.user.school,
    })
    
    return html_to_pdf_response(html_string, f'GatePass_{gate_pass.pass_number}.pdf')
@role_required(*CSO_ROLES)
def gate_pass_cancel(request, pk):
    school = _school(request)
    gate_pass = get_object_or_404(GatePass, pk=pk, school=school)

    if request.method == 'POST':
        gate_pass.status = GatePass.Status.CANCELLED
        gate_pass.save(update_fields=['status', 'updated_at'])
        messages.success(request, f"Pass {gate_pass.pass_number} cancelled.")
        return redirect('cso_gate_pass_list')

    return render(request, 'dashboards/cso/gate_pass_cancel.html', {
        'school': school,
        'gate_pass': gate_pass,
    })


# ==========================================================
# Incidents
# ==========================================================

@role_required(*CSO_ROLES)
def incident_list(request):
    school = _school(request)
    qs = Incident.objects.filter(school=school).select_related(
        'involved_student', 'reported_by',
    )
    status = request.GET.get('status', '').strip()
    severity = request.GET.get('severity', '').strip()
    category = request.GET.get('category', '').strip()
    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)
    if category:
        qs = qs.filter(category=category)

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/cso/incident_list.html', {
        'school': school,
        'incidents': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'status': status,
        'severity': severity,
        'category': category,
        'severity_choices': Incident.Severity.choices,
        'category_choices': Incident.Category.choices,
    })


@role_required(*CSO_ROLES)
def incident_create(request):
    school = _school(request)
    if request.method == 'POST':
        form = IncidentForm(request.POST, school=school)
        if form.is_valid():
            inc = form.save(commit=False)
            inc.school = school
            inc.reported_by = request.user
            inc.save()
            messages.success(request, f"Incident {inc.reference} logged.")
            return redirect('cso_incident_detail', pk=inc.pk)
    else:
        form = IncidentForm(school=school, initial={'occurred_at': timezone.now()})

    return render(request, 'dashboards/cso/incident_form.html', {
        'school': school,
        'form': form,
    })


@role_required(*CSO_ROLES)
def incident_detail(request, pk):
    school = _school(request)
    inc = get_object_or_404(
        Incident.objects.select_related('involved_student', 'reported_by', 'handled_by'),
        pk=pk, school=school,
    )
    return render(request, 'dashboards/cso/incident_detail.html', {
        'school': school,
        'incident': inc,
    })


@role_required(*CSO_ROLES)
def incident_edit(request, pk):
    school = _school(request)
    inc = get_object_or_404(Incident, pk=pk, school=school)

    if request.method == 'POST':
        form = IncidentForm(request.POST, instance=inc, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident updated.")
            return redirect('cso_incident_detail', pk=inc.pk)
    else:
        form = IncidentForm(instance=inc, school=school)

    return render(request, 'dashboards/cso/incident_form.html', {
        'school': school,
        'form': form,
        'incident': inc,
    })


# ==========================================================
# Lost & Found
# ==========================================================

@role_required(*CSO_ROLES)
def lost_item_list(request):
    school = _school(request)
    qs = LostItem.objects.filter(school=school)
    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status=status)

    return render(request, 'dashboards/cso/lost_item_list.html', {
        'school': school,
        'items': qs[:200],
        'total': qs.count(),
        'status': status,
    })


@role_required(*CSO_ROLES)
def lost_item_create(request):
    school = _school(request)
    if request.method == 'POST':
        form = LostItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.school = school
            item.logged_by = request.user
            item.save()
            messages.success(request, "Lost item logged.")
            return redirect('cso_lost_item_list')
    else:
        form = LostItemForm(initial={'found_at': timezone.now()})

    return render(request, 'dashboards/cso/lost_item_form.html', {
        'school': school,
        'form': form,
    })


@role_required(*CSO_ROLES)
def lost_item_claim(request, pk):
    school = _school(request)
    item = get_object_or_404(LostItem, pk=pk, school=school)

    if request.method == 'POST':
        form = ClaimLostItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Item marked as claimed.")
            return redirect('cso_lost_item_list')
    else:
        form = ClaimLostItemForm(instance=item)

    return render(request, 'dashboards/cso/lost_item_claim.html', {
        'school': school,
        'form': form,
        'item': item,
    })


# ==========================================================
# Security Shifts
# ==========================================================

@role_required(*CSO_ROLES)
def shift_list(request):
    school = _school(request)
    shifts = (
        SecurityShift.objects.filter(school=school)
        .select_related('guard')
        .order_by('-shift_date', 'shift_type')
    )
    return render(request, 'dashboards/cso/shift_list.html', {
        'school': school,
        'shifts': shifts[:200],
        'total': shifts.count(),
    })


@role_required(*CSO_ROLES)
def shift_create(request):
    school = _school(request)
    if request.method == 'POST':
        form = SecurityShiftForm(request.POST, school=school)
        if form.is_valid():
            sh = form.save(commit=False)
            sh.school = school
            sh.save()
            messages.success(request, "Shift added to roster.")
            return redirect('cso_shift_list')
    else:
        form = SecurityShiftForm(
            school=school,
            initial={'shift_date': timezone.localdate()},
        )

    return render(request, 'dashboards/cso/shift_form.html', {
        'school': school,
        'form': form,
    })