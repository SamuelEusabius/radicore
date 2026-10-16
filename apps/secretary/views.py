"""
Secretary dashboard views.

Combines:
  - Official visitor coordination (reads from apps.security)
  - Appointments
  - Correspondence
  - Notice board
  - Admission applications
"""
import logging
import logging
from .letter_service import (
    seed_default_templates, render_letter, build_student_context,
)
from .models import (
    Appointment, Correspondence, Notice, AdmissionApplication,
    LetterTemplate, GeneratedLetter, LetterAttachment,
)
from apps.students.models import Student
logger = logging.getLogger(__name__)


def _auto_generate_admission_letter(application, user, school):
    """
    Generates an admission letter on acceptance.
    Uses the school's default admission template.
    """
    from .letter_service import seed_default_templates, render_letter

    seed_default_templates(school)
    template_obj = LetterTemplate.objects.filter(
        school=school, letter_type='admission', is_default_for_type=True
    ).first()

    if not template_obj:
        return None

    ctx = {
        'student_name': application.full_name,
        'admission_number': '—',  # not yet assigned
        'class_level': application.applying_for_class,
        'admission_date': timezone.localdate().strftime('%d %B %Y'),
        'guardian_name': application.guardian_name,
        'school_name': school.name,
        'principal_name': school.principal_name or 'Principal',
        'today': timezone.localdate().strftime('%d %B %Y'),
        'reason': '',
        'custom': '',
    }

    rendered = render_letter(template_obj, ctx)

    return GeneratedLetter.objects.create(
        school=school,
        template=template_obj,
        letter_type='admission',
        recipient_name=application.full_name,
        title=rendered['title'],
        body=rendered['body'],
        closing_line=rendered['closing_line'],
        signatory_name=rendered['signatory_name'],
        signatory_title=rendered['signatory_title'],
        status=GeneratedLetter.Status.ISSUED,
        generated_by=user,
        notes=f"Auto-generated for application {application.reference_number}",
    )
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.security.models import Visitor, GatePass

from .forms import (
    AppointmentForm, AppointmentCompleteForm,
    CorrespondenceForm, NoticeForm, AdmissionApplicationForm,
)
from .models import Appointment, Correspondence, Notice, AdmissionApplication
from .services import (
    notify_host_of_appointment,
    notify_requester_appointment_confirmed,
    notify_requester_appointment_cancelled,
    notify_guardian_application_received,
    notify_guardian_application_status,
    notify_admin_official_visitor,
)


SECRETARY_ROLES = ('secretary', 'principal', 'deputy_admin')


# ==========================================================
# Helpers
# ==========================================================

def _school(request):
    school = getattr(request, 'school', None)
    if not school and request.user.is_authenticated:
        school = getattr(request.user, 'school', None)
    if not school:
        raise PermissionError("No school attached to this request.")
    return school


# ==========================================================
# Dashboard — front desk snapshot
# ==========================================================

@role_required(*SECRETARY_ROLES)
def secretary_dashboard(request):
    school = _school(request)
    today = timezone.localdate()

    # Visitor stats (from CSO module)
    official_pending = Visitor.objects.filter(
        school=school,
        visit_type='official',
        time_out__isnull=True,
    ).count()

    stats = {
        'visitors_today': Visitor.objects.filter(school=school, time_in__date=today).count(),
        'official_pending': official_pending,
        'on_premises': Visitor.objects.filter(school=school, time_out__isnull=True).count(),
        'appointments_today': Appointment.objects.filter(
            school=school, scheduled_date=today
        ).exclude(status__in=('cancelled', 'completed')).count(),
        'open_applications': AdmissionApplication.objects.filter(
            school=school
        ).exclude(status__in=('enrolled', 'rejected', 'withdrawn')).count(),
        'pending_mail': Correspondence.objects.filter(
            school=school, status__in=('received', 'pending')
        ).count(),
    }

    context = {
        'school': school,
        'today': today,
        'stats': stats,
        'todays_appointments': (
            Appointment.objects.filter(school=school, scheduled_date=today)
            .exclude(status__in=('cancelled',))
            .select_related('host_user')
            .order_by('scheduled_time')[:6]
        ),
        'recent_visitors': (
            Visitor.objects.filter(school=school, time_in__date=today)
            .select_related('host_user')
            .order_by('-time_in')[:6]
        ),
        'recent_applications': (
            AdmissionApplication.objects.filter(school=school)
            .order_by('-created_at')[:6]
        ),
        'live_notices': Notice.objects.filter(
            school=school, is_published=True
        ).order_by('-published_at')[:5],
    }
    return render(request, 'dashboards/secretary/dashboard.html', context)


# ==========================================================
# Visitor coordination (reads CSO module)
# ==========================================================

@role_required(*SECRETARY_ROLES)
def visitor_feed(request):
    """
    Secretary's view of the CSO visitor register.
    Highlight official visitors that need coordination.
    """
    school = _school(request)
    qs = Visitor.objects.filter(school=school).select_related(
        'host_user', 'registered_by', 'admin_signed_by',
    )

    filter_type = request.GET.get('filter', '').strip()
    if filter_type == 'official':
        qs = qs.filter(visit_type='official')
    elif filter_type == 'pending_sign':
        qs = qs.filter(visit_type='official', admin_signed_at__isnull=True, time_out__isnull=True)
    elif filter_type == 'on_premises':
        qs = qs.filter(time_out__isnull=True)

    qs = qs.order_by('-time_in')

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'school': school,
        'visitors': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'filter_type': filter_type,
    }
    return render(request, 'dashboards/secretary/visitor_feed.html', context)


@role_required(*SECRETARY_ROLES)
def official_pass_issue(request, visitor_id):
    """
    Secretary issues the official pass for an admin visitor.
    Marks visitor.official_pass_issued_at + notifies the admin host.
    """
    school = _school(request)
    visitor = get_object_or_404(Visitor, pk=visitor_id, school=school)

    if not visitor.is_official:
        messages.warning(request, "This is a standard visitor — no official pass needed.")
        return redirect('secretary_visitor_feed')

    if visitor.official_pass_issued_at:
        messages.info(request, "Official pass was already issued.")
        return redirect('secretary_visitor_detail', pk=visitor.pk)

    if request.method == 'POST':
        visitor.official_pass_issued_at = timezone.now()
        visitor.official_pass_issued_by = request.user
        visitor.status = Visitor.Status.IN_MEETING
        visitor.save()

        # Notify admin host
        try:
            notify_admin_official_visitor(visitor)
        except Exception:
            pass

        messages.success(request, f"Official pass issued for {visitor.full_name}.")
        return redirect('secretary_visitor_detail', pk=visitor.pk)

    return render(request, 'dashboards/secretary/official_pass_issue.html', {
        'school': school,
        'visitor': visitor,
    })


@role_required(*SECRETARY_ROLES)
def visitor_detail(request, pk):
    school = _school(request)
    visitor = get_object_or_404(
        Visitor.objects.select_related(
            'host_user', 'registered_by', 'admin_signed_by',
            'official_pass_issued_by', 'admin_confirmed_by_secretary',
            'logged_out_by',
        ),
        pk=pk, school=school,
    )
    gate_pass = getattr(visitor, 'gate_pass', None)

    return render(request, 'dashboards/secretary/visitor_detail.html', {
        'school': school,
        'visitor': visitor,
        'gate_pass': gate_pass,
    })


@role_required(*SECRETARY_ROLES)
def confirm_admin_signature(request, visitor_id):
    """
    Secretary confirms that the admin host has signed the official pass.
    This updates both Visitor and GatePass.
    """
    school = _school(request)
    visitor = get_object_or_404(Visitor, pk=visitor_id, school=school)

    if not visitor.is_official:
        messages.warning(request, "Only official visitors require admin signatures.")
        return redirect('secretary_visitor_feed')

    if visitor.admin_signed_at:
        messages.info(request, "Signature already confirmed.")
        return redirect('secretary_visitor_detail', pk=visitor.pk)

    if request.method == 'POST':
        signer_name = request.POST.get('signer_name', '').strip()
        signer_user_id = request.POST.get('signer_user') or None
        notes = request.POST.get('signature_notes', '').strip()

        if not signer_name and not signer_user_id:
            messages.error(request, "Enter signer name or pick a user.")
        else:
            with transaction.atomic():
                visitor.admin_signed_at = timezone.now()
                visitor.admin_signed_name = signer_name
                visitor.admin_signature_notes = notes
                if signer_user_id:
                    from apps.accounts.models import User
                    try:
                        visitor.admin_signed_by = User.objects.get(
                            pk=signer_user_id, school=school
                        )
                    except User.DoesNotExist:
                        pass
                visitor.admin_confirmed_by_secretary = request.user
                visitor.admin_confirmed_at = timezone.now()
                visitor.status = Visitor.Status.SIGNED_OUT
                visitor.save()

                # Update gate pass
                gp = getattr(visitor, 'gate_pass', None)
                if gp:
                    gp.signed_by_name = signer_name
                    gp.signed_by_user = visitor.admin_signed_by
                    gp.signed_at = visitor.admin_signed_at
                    gp.status = GatePass.Status.SIGNED
                    gp.save()

            messages.success(request, "Admin signature confirmed.")
            return redirect('secretary_visitor_detail', pk=visitor.pk)

    # For form rendering
    from apps.accounts.models import User
    admin_users = User.objects.filter(school=school).exclude(
        role__in=('student', 'parent')
    ).order_by('first_name', 'last_name')

    return render(request, 'dashboards/secretary/confirm_signature.html', {
        'school': school,
        'visitor': visitor,
        'admin_users': admin_users,
    })


@role_required(*SECRETARY_ROLES)
def checkout_official_visitor(request, visitor_id):
    """Secretary logs out an official visitor after admin signature."""
    school = _school(request)
    visitor = get_object_or_404(Visitor, pk=visitor_id, school=school)

    if not visitor.is_official:
        messages.warning(request, "Only official visitors can be checked out by the Secretary.")
        return redirect('secretary_visitor_feed')

    if visitor.time_out:
        messages.warning(request, f"{visitor.full_name} is already checked out.")
        return redirect('secretary_visitor_detail', pk=visitor.pk)

    if not visitor.admin_signed_at:
        messages.error(
            request,
            "Cannot check out — admin hasn't signed the pass yet. "
            "Confirm signature first."
        )
        return redirect('secretary_visitor_detail', pk=visitor.pk)

    if request.method == 'POST':
        visitor.time_out = timezone.now()
        visitor.logged_out_by = request.user
        visitor.status = Visitor.Status.EXITED
        visitor.save()

        gp = getattr(visitor, 'gate_pass', None)
        if gp and gp.status != GatePass.Status.USED:
            gp.status = GatePass.Status.USED
            gp.save(update_fields=['status', 'updated_at'])

        messages.success(request, f"{visitor.full_name} checked out.")
        return redirect('secretary_visitor_feed')

    return render(request, 'dashboards/secretary/checkout_visitor.html', {
        'school': school,
        'visitor': visitor,
    })


# ==========================================================
# Appointments
# ==========================================================

@role_required(*SECRETARY_ROLES)
def appointment_list(request):
    school = _school(request)
    qs = Appointment.objects.filter(school=school).select_related('host_user')

    status = request.GET.get('status', '').strip()
    when = request.GET.get('when', '').strip()
    search = request.GET.get('q', '').strip()

    if status:
        qs = qs.filter(status=status)
    if when == 'today':
        qs = qs.filter(scheduled_date=timezone.localdate())
    elif when == 'upcoming':
        qs = qs.filter(scheduled_date__gte=timezone.localdate())
    elif when == 'past':
        qs = qs.filter(scheduled_date__lt=timezone.localdate())
    if search:
        qs = qs.filter(
            Q(requester_name__icontains=search)
            | Q(subject__icontains=search)
            | Q(requester_phone__icontains=search)
        )

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/secretary/appointment_list.html', {
        'school': school,
        'appointments': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'status': status,
        'when': when,
        'search': search,
    })


@role_required(*SECRETARY_ROLES)
def appointment_create(request):
    school = _school(request)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, school=school)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.school = school
            appt.created_by = request.user
            appt.save()

            try:
                notify_host_of_appointment(appt)
            except Exception:
                pass

            messages.success(request, "Appointment booked.")
            return redirect('secretary_appointment_detail', pk=appt.pk)
    else:
        form = AppointmentForm(school=school)

    return render(request, 'dashboards/secretary/appointment_form.html', {
        'school': school,
        'form': form,
        'mode': 'create',
    })


@role_required(*SECRETARY_ROLES)
def appointment_detail(request, pk):
    school = _school(request)
    appt = get_object_or_404(
        Appointment.objects.select_related('host_user', 'created_by', 'confirmed_by'),
        pk=pk, school=school,
    )
    return render(request, 'dashboards/secretary/appointment_detail.html', {
        'school': school,
        'appointment': appt,
    })


@role_required(*SECRETARY_ROLES)
def appointment_confirm(request, pk):
    school = _school(request)
    appt = get_object_or_404(Appointment, pk=pk, school=school)

    if request.method == 'POST':
        appt.status = Appointment.Status.CONFIRMED
        appt.confirmed_by = request.user
        appt.confirmed_at = timezone.now()
        appt.save()

        try:
            notify_requester_appointment_confirmed(appt)
        except Exception:
            pass

        messages.success(request, "Appointment confirmed.")
        return redirect('secretary_appointment_detail', pk=appt.pk)

    return render(request, 'dashboards/secretary/appointment_confirm.html', {
        'school': school,
        'appointment': appt,
    })


@role_required(*SECRETARY_ROLES)
def appointment_complete(request, pk):
    school = _school(request)
    appt = get_object_or_404(Appointment, pk=pk, school=school)

    if request.method == 'POST':
        form = AppointmentCompleteForm(request.POST, request.FILES, instance=appt)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.status = Appointment.Status.COMPLETED
            obj.save()
            messages.success(request, "Appointment marked complete.")
            return redirect('secretary_appointment_detail', pk=appt.pk)
    else:
        form = AppointmentCompleteForm(instance=appt, initial={'status': 'completed'})

    return render(request, 'dashboards/secretary/appointment_complete.html', {
        'school': school,
        'appointment': appt,
        'form': form,
    })


@role_required(*SECRETARY_ROLES)
def appointment_cancel(request, pk):
    school = _school(request)
    appt = get_object_or_404(Appointment, pk=pk, school=school)

    if request.method == 'POST':
        appt.status = Appointment.Status.CANCELLED
        appt.save()

        try:
            notify_requester_appointment_cancelled(appt)
        except Exception:
            pass

        messages.success(request, "Appointment cancelled.")
        return redirect('secretary_appointment_list')

    return render(request, 'dashboards/secretary/appointment_cancel.html', {
        'school': school,
        'appointment': appt,
    })


# ==========================================================
# Correspondence
# ==========================================================

@role_required(*SECRETARY_ROLES)
def correspondence_list(request):
    school = _school(request)
    qs = Correspondence.objects.filter(school=school).select_related('assigned_to')

    direction = request.GET.get('direction', '').strip()
    status = request.GET.get('status', '').strip()
    priority = request.GET.get('priority', '').strip()
    search = request.GET.get('q', '').strip()

    if direction:
        qs = qs.filter(direction=direction)
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if search:
        qs = qs.filter(
            Q(subject__icontains=search)
            | Q(correspondent_name__icontains=search)
            | Q(reference_number__icontains=search)
        )

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/secretary/correspondence_list.html', {
        'school': school,
        'items': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'direction': direction,
        'status': status,
        'priority': priority,
        'search': search,
    })


@role_required(*SECRETARY_ROLES)
def correspondence_create(request):
    school = _school(request)

    if request.method == 'POST':
        form = CorrespondenceForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.logged_by = request.user
            obj.save()
            messages.success(request, f"Logged: {obj.reference_number}")
            return redirect('secretary_correspondence_detail', pk=obj.pk)
    else:
        form = CorrespondenceForm(school=school, initial={'direction': 'incoming'})

    return render(request, 'dashboards/secretary/correspondence_form.html', {
        'school': school,
        'form': form,
        'mode': 'create',
    })


@role_required(*SECRETARY_ROLES)
def correspondence_detail(request, pk):
    school = _school(request)
    item = get_object_or_404(
        Correspondence.objects.select_related('assigned_to', 'logged_by'),
        pk=pk, school=school,
    )
    return render(request, 'dashboards/secretary/correspondence_detail.html', {
        'school': school,
        'item': item,
    })


@role_required(*SECRETARY_ROLES)
def correspondence_edit(request, pk):
    school = _school(request)
    item = get_object_or_404(Correspondence, pk=pk, school=school)

    if request.method == 'POST':
        form = CorrespondenceForm(request.POST, request.FILES, instance=item, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, "Correspondence updated.")
            return redirect('secretary_correspondence_detail', pk=item.pk)
    else:
        form = CorrespondenceForm(instance=item, school=school)

    return render(request, 'dashboards/secretary/correspondence_form.html', {
        'school': school,
        'form': form,
        'item': item,
        'mode': 'edit',
    })


# ==========================================================
# Notice Board
# ==========================================================

@role_required(*SECRETARY_ROLES)
def notice_list(request):
    school = _school(request)
    qs = Notice.objects.filter(school=school).select_related('posted_by')
    audience = request.GET.get('audience', '').strip()
    if audience:
        qs = qs.filter(audience=audience)

    return render(request, 'dashboards/secretary/notice_list.html', {
        'school': school,
        'notices': qs[:100],
        'total': qs.count(),
        'audience': audience,
    })


@role_required(*SECRETARY_ROLES)
def notice_create(request):
    school = _school(request)

    if request.method == 'POST':
        form = NoticeForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.posted_by = request.user
            if obj.is_published and not obj.published_at:
                obj.published_at = timezone.now()
            obj.save()
            messages.success(request, "Notice saved.")
            return redirect('secretary_notice_list')
    else:
        form = NoticeForm()

    return render(request, 'dashboards/secretary/notice_form.html', {
        'school': school,
        'form': form,
    })


@role_required(*SECRETARY_ROLES)
def notice_edit(request, pk):
    school = _school(request)
    notice = get_object_or_404(Notice, pk=pk, school=school)

    if request.method == 'POST':
        form = NoticeForm(request.POST, request.FILES, instance=notice)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.is_published and not obj.published_at:
                obj.published_at = timezone.now()
            obj.save()
            messages.success(request, "Notice updated.")
            return redirect('secretary_notice_list')
    else:
        form = NoticeForm(instance=notice)

    return render(request, 'dashboards/secretary/notice_form.html', {
        'school': school,
        'form': form,
        'notice': notice,
    })


# ==========================================================
# Admission Applications
# ==========================================================

@role_required(*SECRETARY_ROLES)
def application_list(request):
    school = _school(request)
    qs = AdmissionApplication.objects.filter(school=school)

    status = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(guardian_name__icontains=search)
            | Q(reference_number__icontains=search)
        )

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/secretary/application_list.html', {
        'school': school,
        'applications': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'status': status,
        'search': search,
    })


@role_required(*SECRETARY_ROLES)
def application_create(request):
    school = _school(request)

    if request.method == 'POST':
        form = AdmissionApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.school = school
            obj.received_by = request.user
            obj.save()

            try:
                notify_guardian_application_received(obj)
            except Exception:
                pass

            messages.success(request, f"Application {obj.reference_number} recorded.")
            return redirect('secretary_application_detail', pk=obj.pk)
    else:
        form = AdmissionApplicationForm(initial={'status': 'new'})

    return render(request, 'dashboards/secretary/application_form.html', {
        'school': school,
        'form': form,
        'mode': 'create',
    })


@role_required(*SECRETARY_ROLES)
def application_detail(request, pk):
    school = _school(request)
    app = get_object_or_404(AdmissionApplication, pk=pk, school=school)
    return render(request, 'dashboards/secretary/application_detail.html', {
        'school': school,
        'application': app,
    })


@role_required(*SECRETARY_ROLES)
def application_edit(request, pk):
    school = _school(request)
    app = get_object_or_404(AdmissionApplication, pk=pk, school=school)

    if request.method == 'POST':
        old_status = app.status
        form = AdmissionApplicationForm(request.POST, request.FILES, instance=app)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.reviewed_by = request.user
            obj.save()

            if obj.status != old_status:
                try:
                    notify_guardian_application_status(obj)
                except Exception:
                    pass

                # Auto-generate admission letter when status becomes accepted/enrolled
                if obj.status in ('accepted', 'enrolled') and not obj.converted_student:
                    try:
                        _auto_generate_admission_letter(obj, request.user, school)
                        messages.info(request, "Admission letter auto-generated.")
                    except Exception as e:
                        logger.exception("Auto admission letter failed: %s", e)

            messages.success(request, "Application updated.")
            return redirect('secretary_application_detail', pk=app.pk)
    else:
        form = AdmissionApplicationForm(instance=app)

    return render(request, 'dashboards/secretary/application_form.html', {
        'school': school,
        'form': form,
        'application': app,
        'mode': 'edit',
    })
    
    from django.db import transaction
from .letter_service import (
    seed_default_templates, render_letter, build_student_context, DEFAULT_TEMPLATES
)
from .models import LetterTemplate, GeneratedLetter
from apps.students.models import Student


# ==========================================================
# LETTER TEMPLATES
# ==========================================================

@role_required(*SECRETARY_ROLES)
def letter_template_list(request):
    school = _school(request)

    # Seed defaults on first visit
    seed_default_templates(school)

    templates_qs = LetterTemplate.objects.filter(school=school).order_by(
        'letter_type', '-is_default_for_type', 'name'
    )

    return render(request, 'dashboards/secretary/letter_template_list.html', {
        'school': school,
        'templates': templates_qs,
        'total': templates_qs.count(),
    })


@role_required(*SECRETARY_ROLES)
def letter_template_edit(request, pk):
    school = _school(request)
    template = get_object_or_404(LetterTemplate, pk=pk, school=school)

    if request.method == 'POST':
        template.name = request.POST.get('name', '').strip() or template.name
        template.title = request.POST.get('title', '').strip() or template.title
        template.body_template = request.POST.get('body_template', '').strip() or template.body_template
        template.closing_line = request.POST.get('closing_line', '').strip()
        template.signatory_name = request.POST.get('signatory_name', '').strip()
        template.signatory_title = request.POST.get('signatory_title', '').strip()
        template.is_active = request.POST.get('is_active') == 'on'
        template.save()
        messages.success(request, "Template updated.")
        return redirect('secretary_letter_template_list')

    return render(request, 'dashboards/secretary/letter_template_form.html', {
        'school': school,
        'template': template,
    })


# ==========================================================
# GENERATED LETTERS
# ==========================================================

@role_required(*SECRETARY_ROLES)
def letter_list(request):
    school = _school(request)
    qs = GeneratedLetter.objects.filter(school=school).select_related(
        'student', 'template', 'generated_by',
    )

    letter_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()
    search = request.GET.get('q', '').strip()

    if letter_type:
        qs = qs.filter(letter_type=letter_type)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(reference_number__icontains=search)
            | Q(title__icontains=search)
            | Q(recipient_name__icontains=search)
            | Q(student__first_name__icontains=search)
            | Q(student__last_name__icontains=search)
        )

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboards/secretary/letter_list.html', {
        'school': school,
        'letters': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total': qs.count(),
        'letter_type': letter_type,
        'status': status,
        'search': search,
        'letter_type_choices': LetterTemplate.LetterType.choices,
    })


@role_required(*SECRETARY_ROLES)
def letter_create(request):
    school = _school(request)
    seed_default_templates(school)

    if request.method == 'POST':
        letter_type = request.POST.get('letter_type', '').strip()
        template_id = request.POST.get('template_id') or None
        student_id = request.POST.get('student_id') or None
        recipient_name = request.POST.get('recipient_name', '').strip()
        reason = request.POST.get('reason', '').strip()
        custom_extra = request.POST.get('custom_extra', '').strip()
        body_override = request.POST.get('body_override', '').strip()

        if not letter_type:
            messages.error(request, "Please pick a letter type.")
        else:
            template_obj = None
            if template_id:
                try:
                    template_obj = LetterTemplate.objects.get(pk=template_id, school=school)
                except LetterTemplate.DoesNotExist:
                    pass
            if not template_obj:
                template_obj = LetterTemplate.objects.filter(
                    school=school, letter_type=letter_type, is_default_for_type=True
                ).first()

            if not template_obj:
                messages.error(request, "No template found for this letter type.")
            else:
                student_obj = None
                if student_id:
                    try:
                        student_obj = Student.objects.get(pk=student_id, school=school)
                    except Student.DoesNotExist:
                        pass

                # Build the context
                if student_obj:
                    ctx = build_student_context(
                        student_obj, school,
                        reason=reason,
                        extra={'custom': custom_extra},
                    )
                else:
                    ctx = {
                        'student_name': recipient_name or '—',
                        'admission_number': '—',
                        'class_level': '—',
                        'admission_date': '—',
                        'guardian_name': 'Parent/Guardian',
                        'school_name': school.name,
                        'principal_name': school.principal_name or 'Principal',
                        'today': timezone.localdate().strftime('%d %B %Y'),
                        'reason': reason,
                        'custom': custom_extra,
                    }

                # If user supplied a body, render that instead of template body
                if body_override:
                    from django.template import Context, Template
                    django_ctx = Context(ctx)
                    rendered = {
                        'title': Template(template_obj.title).render(django_ctx).strip(),
                        'body': Template(body_override).render(django_ctx).strip(),
                        'closing_line': Template(template_obj.closing_line or '').render(django_ctx).strip(),
                        'signatory_name': (template_obj.signatory_name or ctx.get('principal_name', '')).strip(),
                        'signatory_title': Template(template_obj.signatory_title or '').render(django_ctx).strip(),
                    }
                else:
                    rendered = render_letter(template_obj, ctx)

                letter = GeneratedLetter.objects.create(
                    school=school,
                    template=template_obj,
                    letter_type=letter_type,
                    student=student_obj,
                    recipient_name=recipient_name,
                    title=rendered['title'],
                    body=rendered['body'],
                    closing_line=rendered['closing_line'],
                    signatory_name=rendered['signatory_name'],
                    signatory_title=rendered['signatory_title'],
                    status=GeneratedLetter.Status.ISSUED,
                    generated_by=request.user,
                )

                # Process attachments
                attach_types = request.POST.getlist('attach_type[]')
                attach_titles = request.POST.getlist('attach_title[]')
                attach_files = request.FILES.getlist('attach_file[]')

                saved_attachments = 0
                for dtype, title, file in zip(attach_types, attach_titles, attach_files):
                    if not file:
                        continue
                    LetterAttachment.objects.create(
                        letter=letter,
                        doc_type=dtype or 'other',
                        title=title.strip() or file.name,
                        file=file,
                        uploaded_by=request.user,
                    )
                    saved_attachments += 1

                msg = f"Letter {letter.reference_number} generated."
                if saved_attachments:
                    msg += f" {saved_attachments} attachment(s) saved."
                messages.success(request, msg)
                return redirect('secretary_letter_detail', pk=letter.pk)

    students = Student.objects.filter(school=school).order_by('first_name', 'last_name')
    templates_qs = LetterTemplate.objects.filter(
        school=school, is_active=True
    ).order_by('letter_type', '-is_default_for_type')

    return render(request, 'dashboards/secretary/letter_form.html', {
        'school': school,
        'students': students,
        'templates': templates_qs,
        'letter_type_choices': LetterTemplate.LetterType.choices,
    })


@role_required(*SECRETARY_ROLES)
def letter_detail(request, pk):
    school = _school(request)
    letter = get_object_or_404(
        GeneratedLetter.objects.select_related('student', 'template', 'generated_by'),
        pk=pk, school=school,
    )
    return render(request, 'dashboards/secretary/letter_detail.html', {
        'school': school,
        'letter': letter,
    })


@role_required(*SECRETARY_ROLES)
def letter_print(request, pk):
    """Print-ready letterhead PDF view."""
    school = _school(request)
    letter = get_object_or_404(
        GeneratedLetter.objects.select_related('student', 'template'),
        pk=pk, school=school,
    )
    from apps.core.pdf_utils import build_pdf_context

    context = build_pdf_context(
        school, request.user,
        letter=letter,
        student=letter.student,
        auto_print=request.GET.get('auto', '1') == '1',
    )
    return render(request, 'pdf/letter_print.html', context)


@role_required(*SECRETARY_ROLES)
def letter_mark_collected(request, pk):
    school = _school(request)
    letter = get_object_or_404(GeneratedLetter, pk=pk, school=school)

    if request.method == 'POST':
        letter.status = GeneratedLetter.Status.COLLECTED
        letter.collected_at = timezone.now()
        letter.issued_to = request.POST.get('issued_to', '').strip()
        letter.save()
        messages.success(request, "Letter marked as collected.")
        return redirect('secretary_letter_detail', pk=letter.pk)

    return render(request, 'dashboards/secretary/letter_collect.html', {
        'school': school,
        'letter': letter,
    })
    
    

# ==========================================================
# NOTICE PRINTING
# ==========================================================

@role_required(*SECRETARY_ROLES)
def notice_print(request, pk):
    """Print-friendly single notice."""
    school = _school(request)
    notice = get_object_or_404(Notice, pk=pk, school=school)

    return render(request, 'pdf/notice_print.html', {
        'school': school,
        'notice': notice,
        'generated_by': request.user,
        'generated_on': timezone.now(),
        'auto_print': request.GET.get('auto', '1') == '1',
    })


@role_required(*SECRETARY_ROLES)
def notice_print_all(request):
    """Bulk-print all live notices, one per page."""
    school = _school(request)
    notices = (
        Notice.objects.filter(school=school, is_published=True)
        .order_by('-priority', '-published_at')
    )
    notices = [n for n in notices if n.is_live]

    return render(request, 'pdf/notice_print_all.html', {
        'school': school,
        'notices': notices,
        'generated_by': request.user,
        'generated_on': timezone.now(),
        'auto_print': request.GET.get('auto', '1') == '1',
    })