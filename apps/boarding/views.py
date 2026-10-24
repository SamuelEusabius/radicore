"""
Boarding Master views — full CRUD for dormitories, beds, and assignments.

Every view:
  - requires login
  - requires role = 'boarding_master' or 'principal'
  - requires request.user.school to be set
  - scopes every queryset to request.user.school
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import (
    AssignmentCheckoutForm,
    AssignmentForm,
    BedBulkForm,
    BedForm,
    DormitoryForm,
)
from .models import BoardingAssignment, BoardingBed, BoardingDormitory
from .services import (
    BoardingError,
    assign_bed,
    bulk_create_beds,
    checkout_bed,
    dormitory_has_active_assignments,
    transfer_bed,
)

ALLOWED_ROLES = ('boarding_master', 'principal')


def boarding_master_required(view_func):
    """Login + role + school guard, all in one decorator."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if getattr(user, 'role', None) not in ALLOWED_ROLES:
            raise PermissionDenied("Boarding module is restricted to the Boarding Master.")
        if not getattr(user, 'school_id', None):
            raise PermissionDenied("Your account is not linked to a school.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ============================================================
# DASHBOARD
# ============================================================

@boarding_master_required
def boarding_index(request):
    school = request.user.school
    dorms = (
        BoardingDormitory.objects
        .filter(school=school)
        .annotate(
            bed_total=Count('beds', distinct=True),
            bed_occupied=Count('beds', filter=Q(beds__is_occupied=True), distinct=True),
        )
        .order_by('name')
    )
    total_beds = sum(d.bed_total for d in dorms)
    total_occupied = sum(d.bed_occupied for d in dorms)
    occupancy_pct = round((total_occupied / total_beds) * 100) if total_beds else 0

    recent_assignments = (
        BoardingAssignment.objects
        .filter(student__school=school, status=BoardingAssignment.Status.ACTIVE)
        .select_related('student', 'dormitory', 'bed')
        .order_by('-assigned_at')[:10]
    )

    return render(request, 'boarding/index.html', {
        'dorms': dorms,
        'dorm_count': len(dorms),
        'total_beds': total_beds,
        'total_occupied': total_occupied,
        'total_available': total_beds - total_occupied,
        'occupancy_pct': occupancy_pct,
        'recent_assignments': recent_assignments,
    })


# ============================================================
# DORMITORIES
# ============================================================

@boarding_master_required
def dormitory_manage(request):
    school = request.user.school
    dorms = (
        BoardingDormitory.objects
        .filter(school=school)
        .annotate(
            bed_total=Count('beds', distinct=True),
            bed_occupied=Count('beds', filter=Q(beds__is_occupied=True), distinct=True),
        )
        .order_by('name')
    )
    return render(request, 'boarding/dormitory_manage.html', {'dorms': dorms})


@boarding_master_required
def dormitory_create(request):
    school = request.user.school
    if request.method == 'POST':
        form = DormitoryForm(request.POST, school=school)
        if form.is_valid():
            dorm = form.save(commit=False)
            dorm.school = school
            dorm.save()
            messages.success(request, f"Dormitory “{dorm.name}” created.")
            return redirect('boarding:dormitory_manage')
    else:
        form = DormitoryForm(school=school)
    return render(request, 'boarding/dormitory_form.html', {'form': form, 'mode': 'create'})


@boarding_master_required
def dormitory_edit(request, pk):
    school = request.user.school
    dorm = get_object_or_404(BoardingDormitory, pk=pk, school=school)
    if request.method == 'POST':
        form = DormitoryForm(request.POST, instance=dorm, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Dormitory “{dorm.name}” updated.")
            return redirect('boarding:dormitory_manage')
    else:
        form = DormitoryForm(instance=dorm, school=school)
    return render(request, 'boarding/dormitory_form.html', {
        'form': form, 'mode': 'edit', 'dorm': dorm,
    })


@boarding_master_required
@require_POST
def dormitory_delete(request, pk):
    school = request.user.school
    dorm = get_object_or_404(BoardingDormitory, pk=pk, school=school)
    if dormitory_has_active_assignments(dorm):
        messages.error(
            request,
            f"“{dorm.name}” has active assignments. Check out all students first.",
        )
        return redirect('boarding:dormitory_manage')
    name = dorm.name
    dorm.delete()
    messages.success(request, f"Dormitory “{name}” deleted.")
    return redirect('boarding:dormitory_manage')


# ============================================================
# BEDS
# ============================================================

@boarding_master_required
def bed_manage(request):
    school = request.user.school
    dorms = (
        BoardingDormitory.objects
        .filter(school=school)
        .annotate(
            bed_total=Count('beds', distinct=True),
            bed_occupied=Count('beds', filter=Q(beds__is_occupied=True), distinct=True),
        )
        .order_by('name')
    )
    dorm_id = request.GET.get('dormitory')
    beds_qs = (
        BoardingBed.objects
        .filter(dormitory__school=school)
        .select_related('dormitory')
        .order_by('dormitory__name', 'bed_number')
    )
    selected_dorm = None
    if dorm_id:
        selected_dorm = get_object_or_404(BoardingDormitory, pk=dorm_id, school=school)
        beds_qs = beds_qs.filter(dormitory=selected_dorm)

    return render(request, 'boarding/bed_manage.html', {
        'dorms': dorms,
        'beds': beds_qs,
        'selected_dorm': selected_dorm,
    })


@boarding_master_required
def bed_create(request):
    school = request.user.school
    if request.method == 'POST':
        form = BedForm(request.POST, school=school)
        if form.is_valid():
            bed = form.save()
            messages.success(request, f"Bed {bed.bed_number} added to {bed.dormitory.name}.")
            return redirect(f"{reverse('boarding:bed_manage')}?dormitory={bed.dormitory_id}")
    else:
        initial = {}
        if request.GET.get('dormitory'):
            initial['dormitory'] = request.GET['dormitory']
        form = BedForm(initial=initial, school=school)
    return render(request, 'boarding/bed_form.html', {'form': form, 'mode': 'create'})


@boarding_master_required
def bed_edit(request, pk):
    school = request.user.school
    bed = get_object_or_404(BoardingBed, pk=pk, dormitory__school=school)
    if request.method == 'POST':
        form = BedForm(request.POST, instance=bed, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Bed {bed.bed_number} updated.")
            return redirect(f"{reverse('boarding:bed_manage')}?dormitory={bed.dormitory_id}")
    else:
        form = BedForm(instance=bed, school=school)
    return render(request, 'boarding/bed_form.html', {'form': form, 'mode': 'edit', 'bed': bed})


@boarding_master_required
@require_POST
def bed_delete(request, pk):
    school = request.user.school
    bed = get_object_or_404(BoardingBed, pk=pk, dormitory__school=school)
    if bed.is_occupied:
        messages.error(request, f"Bed {bed.bed_number} is occupied. Check out the student first.")
        return redirect(f"{reverse('boarding:bed_manage')}?dormitory={bed.dormitory_id}")
    dorm_id = bed.dormitory_id
    label = bed.bed_number
    bed.delete()
    messages.success(request, f"Bed {label} deleted.")
    return redirect(f"{reverse('boarding:bed_manage')}?dormitory={dorm_id}")


@boarding_master_required
def bed_bulk_create(request):
    school = request.user.school
    if request.method == 'POST':
        form = BedBulkForm(request.POST, school=school)
        if form.is_valid():
            try:
                created, skipped = bulk_create_beds(
                    dormitory=form.cleaned_data['dormitory'],
                    prefix=form.cleaned_data['prefix'],
                    start=form.cleaned_data['start'],
                    count=form.cleaned_data['count'],
                    width=form.cleaned_data['width'],
                )
            except BoardingError as e:
                messages.error(request, str(e))
            else:
                msg = f"{created} bed(s) created."
                if skipped:
                    msg += f" {skipped} skipped (already existed)."
                messages.success(request, msg)
                return redirect(
                    f"{reverse('boarding:bed_manage')}?dormitory={form.cleaned_data['dormitory'].pk}"
                )
    else:
        initial = {}
        if request.GET.get('dormitory'):
            initial['dormitory'] = request.GET['dormitory']
        form = BedBulkForm(initial=initial, school=school)
    return render(request, 'boarding/bed_bulk_form.html', {'form': form})


# ============================================================
# ASSIGNMENTS
# ============================================================

@boarding_master_required
def assignment_list(request):
    school = request.user.school
    status = request.GET.get('status', 'active')
    valid = {'active', 'transferred', 'checked_out', 'suspended', 'all'}
    if status not in valid:
        status = 'active'

    qs = (
        BoardingAssignment.objects
        .filter(student__school=school)
        .select_related('student', 'dormitory', 'bed')
        .order_by('-assigned_at')
    )
    if status != 'all':
        qs = qs.filter(status=status)

    transfer_beds = (
        BoardingBed.objects
        .filter(dormitory__school=school, is_occupied=False)
        .select_related('dormitory')
        .order_by('dormitory__name', 'bed_number')
    )

    return render(request, 'boarding/assignment_list.html', {
        'assignments': qs,
        'status': status,
        'transfer_beds': transfer_beds,
    })


@boarding_master_required
def assignment_create(request):
    school = request.user.school
    if request.method == 'POST':
        form = AssignmentForm(request.POST, school=school)
        if form.is_valid():
            try:
                assign_bed(
                    student=form.cleaned_data['student'],
                    bed=form.cleaned_data['bed'],
                    user=request.user,
                    notes=form.cleaned_data.get('notes', ''),
                )
            except BoardingError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Student assigned to bed.")
                return redirect('boarding:assignment_list')
    else:
        form = AssignmentForm(school=school)
    return render(request, 'boarding/assignment_form.html', {'form': form})


@boarding_master_required
@require_POST
def assignment_transfer(request, pk):
    school = request.user.school
    assignment = get_object_or_404(
        BoardingAssignment, pk=pk, student__school=school,
        status=BoardingAssignment.Status.ACTIVE,
    )
    new_bed_id = request.POST.get('new_bed')
    if not new_bed_id:
        messages.error(request, "Select a target bed.")
        return redirect('boarding:assignment_list')
    new_bed = get_object_or_404(
        BoardingBed, pk=new_bed_id, dormitory__school=school, is_occupied=False,
    )
    try:
        transfer_bed(assignment, new_bed, user=request.user)
    except BoardingError as e:
        messages.error(request, str(e))
    else:
        messages.success(
            request,
            f"{assignment.student} transferred to {new_bed.dormitory.name} · {new_bed.bed_number}.",
        )
    return redirect('boarding:assignment_list')


@boarding_master_required
def assignment_checkout(request, pk):
    school = request.user.school
    assignment = get_object_or_404(
        BoardingAssignment, pk=pk, student__school=school,
        status=BoardingAssignment.Status.ACTIVE,
    )
    if request.method == 'POST':
        form = AssignmentCheckoutForm(request.POST)
        if form.is_valid():
            try:
                checkout_bed(assignment, user=request.user, reason=form.cleaned_data['reason'])
            except BoardingError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"{assignment.student} checked out.")
                return redirect('boarding:assignment_list')
    else:
        form = AssignmentCheckoutForm()
    return render(request, 'boarding/assignment_checkout.html', {
        'assignment': assignment, 'form': form,
    })
    
    

# ============================================================
# ROSTER DOWNLOADS — CSV & PDF
# ============================================================

import csv
from io import BytesIO

from django.http import HttpResponse
from django.template.loader import get_template


def _roster_qs(request, dormitory=None):
    """
    Return the queryset of ACTIVE boarding assignments scoped to the
    requesting user's school, optionally filtered by dormitory.
    """
    qs = (
        BoardingAssignment.objects
        .filter(
            student__school=request.user.school,
            status=BoardingAssignment.Status.ACTIVE,
        )
        .select_related('student', 'dormitory', 'bed')
        .order_by('dormitory__name', 'bed__bed_number', 'student__admission_number')
    )
    if dormitory is not None:
        qs = qs.filter(dormitory=dormitory)
    return qs


@boarding_master_required
def boarders_csv(request):
    """CSV of every active boarder in the school."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="boarders_all.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Admission No', 'First Name', 'Last Name', 'Gender', 'Class',
        'Dormitory', 'Bed', 'Guardian', 'Guardian Phone', 'Assigned At',
    ])
    for a in _roster_qs(request):
        writer.writerow([
            a.student.admission_number,
            a.student.first_name,
            a.student.last_name,
            a.student.gender,
            a.student.class_level,
            a.dormitory.name,
            a.bed.bed_number,
            a.student.guardian_name,
            a.student.guardian_phone,
            a.assigned_at.strftime('%Y-%m-%d') if a.assigned_at else '',
        ])
    return response


@boarding_master_required
def boarders_by_house_csv(request, dormitory_id):
    """CSV of active boarders in one dormitory."""
    school = request.user.school
    dorm = get_object_or_404(BoardingDormitory, pk=dormitory_id, school=school)

    response = HttpResponse(content_type='text/csv')
    safe_name = (dorm.name or 'house').replace(' ', '_').replace('/', '-')
    response['Content-Disposition'] = f'attachment; filename="boarders_{safe_name}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Admission No', 'First Name', 'Last Name', 'Gender', 'Class',
        'Dormitory', 'Bed', 'Guardian', 'Guardian Phone', 'Assigned At',
    ])
    for a in _roster_qs(request, dormitory=dorm):
        writer.writerow([
            a.student.admission_number,
            a.student.first_name,
            a.student.last_name,
            a.student.gender,
            a.student.class_level,
            a.dormitory.name,
            a.bed.bed_number,
            a.student.guardian_name,
            a.student.guardian_phone,
            a.assigned_at.strftime('%Y-%m-%d') if a.assigned_at else '',
        ])
    return response


@boarding_master_required
def boarders_pdf(request):
    """PDF roster of every active boarder, grouped by dormitory."""
    from xhtml2pdf import pisa

    assignments = list(_roster_qs(request))
    # Group by dormitory
    grouped = {}
    for a in assignments:
        grouped.setdefault(a.dormitory, []).append(a)
    groups = sorted(
        ((dorm, rows) for dorm, rows in grouped.items()),
        key=lambda item: item[0].name,
    )

    template = get_template('pdf/boarding_roster.html')
    html = template.render({
        'school': request.user.school,
        'generated_by': request.user,
        'groups': groups,
        'total': len(assignments),
        'scope_label': 'All Dormitories',
    })

    buffer = BytesIO()
    pisa.CreatePDF(src=html, dest=buffer, encoding='utf-8')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="boarding_roster_all.pdf"'
    return response


@boarding_master_required
def boarders_by_house_pdf(request, dormitory_id):
    """PDF roster of active boarders in one dormitory."""
    from xhtml2pdf import pisa

    school = request.user.school
    dorm = get_object_or_404(BoardingDormitory, pk=dormitory_id, school=school)
    assignments = list(_roster_qs(request, dormitory=dorm))
    groups = [(dorm, assignments)]

    template = get_template('pdf/boarding_roster.html')
    html = template.render({
        'school': school,
        'generated_by': request.user,
        'groups': groups,
        'total': len(assignments),
        'scope_label': dorm.name,
    })

    buffer = BytesIO()
    pisa.CreatePDF(src=html, dest=buffer, encoding='utf-8')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    safe_name = (dorm.name or 'house').replace(' ', '_').replace('/', '-')
    response['Content-Disposition'] = f'inline; filename="boarding_roster_{safe_name}.pdf"'
    return response