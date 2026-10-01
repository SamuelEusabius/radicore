"""
Communication views:
- In-app messages (inbox, sent, compose, detail, archive, delete)
- Notifications (list, mark read)
- Smart alerts (dashboard, resolve, dismiss, run scan, admin)
- SMS (bulk, test)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
    class_teacher_only,
)


@login_required
def notifications_list(request):
    """List user's notifications with filters and grouping."""
    from apps.notifications.models import Notification
    from django.db.models import Q, Count
    from django.core.paginator import Paginator
    from datetime import timedelta
    from django.utils import timezone

    base_qs = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    channel_filter = request.GET.get('channel', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(message__icontains=search) |
            Q(description__icontains=search)
        )

    if channel_filter in ('email', 'sms', 'in_app'):
        qs = qs.filter(channel=channel_filter)

    if status_filter == 'unread':
        qs = qs.filter(is_read=False)
    elif status_filter == 'read':
        qs = qs.filter(is_read=True)

    # ---------- Stats ----------
    stats = {
        'total': base_qs.count(),
        'unread': base_qs.filter(is_read=False).count(),
        'in_app': base_qs.filter(channel='in_app').count(),
        'sms': base_qs.filter(channel='sms').count(),
        'email': base_qs.filter(channel='email').count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ---------- Group by date ----------
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    groups = {
        'today': [],
        'yesterday': [],
        'this_week': [],
        'older': [],
    }

    for n in page_obj:
        n_date = n.created_at.date()
        if n_date == today:
            groups['today'].append(n)
        elif n_date == yesterday:
            groups['yesterday'].append(n)
        elif n_date >= week_ago:
            groups['this_week'].append(n)
        else:
            groups['older'].append(n)

    return render(request, 'dashboard/notifications.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'groups': groups,
        'search': search,
        'channel_filter': channel_filter,
        'status_filter': status_filter,
        'total_filtered': qs.count(),
    })


@login_required
def mark_notification_read(request, notif_id):
    from apps.notifications.models import Notification
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return redirect('notifications_list')


@login_required
def alerts_dashboard(request):
    from apps.notifications.models import Alert

    user = request.user

    if user.role == 'super_admin':
        alerts = Alert.objects.all()
    elif user.school:
        alerts = Alert.objects.filter(school=user.school)
    else:
        alerts = Alert.objects.none()

    severity = request.GET.get('severity', '')
    status = request.GET.get('status', '')
    category = request.GET.get('category', '')

    if severity:
        alerts = alerts.filter(severity=severity)
    if status:
        alerts = alerts.filter(status=status)
    if category:
        alerts = alerts.filter(category=category)

    all_alerts = Alert.objects.filter(school=user.school) if user.school else Alert.objects.all()
    counts = {
        'new': all_alerts.filter(status='new').count(),
        'critical': all_alerts.filter(severity='critical', status='new').count(),
        'high': all_alerts.filter(severity='high', status='new').count(),
        'medium': all_alerts.filter(severity='medium', status='new').count(),
        'low': all_alerts.filter(severity='low', status='new').count(),
    }

    return render(request, 'dashboard/alerts.html', {
        'alerts': alerts.select_related('school', 'resolved_by'),
        'counts': counts,
        'filter_severity': severity,
        'filter_status': status,
        'filter_category': category,
    })


@login_required
def alert_resolve(request, alert_id):
    from apps.notifications.models import Alert

    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    alert = get_object_or_404(Alert, id=alert_id)

    if request.user.role != 'super_admin' and alert.school != request.user.school:
        return redirect('dashboard_home')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        alert.resolve(request.user, notes)
        messages.success(request, f'Alert resolved: {alert.title}')
        return redirect('alerts_dashboard')

    return render(request, 'dashboard/alert_resolve.html', {'alert': alert})


@login_required
def alert_dismiss(request, alert_id):
    from apps.notifications.models import Alert

    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    alert = get_object_or_404(Alert, id=alert_id)

    if request.user.role != 'super_admin' and alert.school != request.user.school:
        return redirect('dashboard_home')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        alert.dismiss(request.user, notes)
        messages.success(request, 'Alert dismissed.')
        return redirect('alerts_dashboard')

    return render(request, 'dashboard/alert_dismiss.html', {'alert': alert})


@login_required
def run_scan(request):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.services.smart_alerts import run_all_detections

    try:
        school = request.user.school if request.user.role != 'super_admin' else None
        count = run_all_detections(school)
        if count:
            messages.success(request, f'Scan complete. {count} new alert(s) found.')
        else:
            messages.info(request, 'Scan complete. No new alerts.')
    except Exception as e:
        messages.error(request, f'Scan failed: {e}')

    return redirect('alerts_dashboard')


@login_required
def send_test_sms_view(request):
    """Admin page to send a test SMS."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    result = None

    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        message = request.POST.get('message', 'Test SMS from School MS').strip()

        if not phone:
            messages.error(request, 'Phone number required.')
        else:
            try:
                from apps.notifications.services.sms import send_sms
                result = send_sms(phone, message)

                if result.get('success'):
                    messages.success(request, f'SMS sent to {phone}. Check your phone.')
                else:
                    messages.error(request, f'Failed: {result.get("message")}')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    return render(request, 'dashboard/test_sms.html', {'result': result})


@login_required
def bulk_sms(request):
    """Send bulk SMS to groups of parents."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.parents.models import Parent
    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.finance.models import Invoice
    from apps.notifications.services.sms import send_bulk_sms, normalize_phone

    school = request.user.school
    all_parents = Parent.objects.filter(user__school=school).select_related('user')

    unpaid_student_ids = Invoice.objects.filter(
        student__school=school,
        status__in=['unpaid', 'partial', 'overdue'],
    ).values_list('student_id', flat=True).distinct()

    unpaid_parents = Parent.objects.filter(
        user__school=school, students__id__in=unpaid_student_ids
    ).distinct()

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    def count_with_phones(qs):
        n = 0
        for p in qs:
            phone = p.user.phone or p.phone
            if phone and normalize_phone(phone):
                n += 1
        return n

    counts = {
        'all': count_with_phones(all_parents),
        'unpaid': count_with_phones(unpaid_parents),
    }

    result = None
    if request.method == 'POST':
        group = request.POST.get('group', 'all')
        class_id = request.POST.get('class_id')
        custom_numbers = request.POST.get('custom_numbers', '').strip()
        message = request.POST.get('message', '').strip()

        if not message:
            messages.error(request, 'Message cannot be empty.')
        else:
            phones = []

            if group == 'custom':
                raw = custom_numbers.replace('\n', ',').split(',')
                for num in raw:
                    num = num.strip()
                    if num and normalize_phone(num):
                        phones.append(num)
            elif group == 'unpaid':
                for p in unpaid_parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)
            elif group == 'class' and class_id:
                student_ids = Student.objects.filter(
                    school=school, class_level=class_id, is_active=True
                ).values_list('id', flat=True)
                parents = Parent.objects.filter(
                    user__school=school, students__id__in=student_ids
                ).distinct()
                for p in parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)
            else:
                for p in all_parents:
                    phone = p.user.phone or p.phone
                    if phone:
                        phones.append(phone)

            phones = list(set(phones))

            if not phones:
                messages.error(request, 'No valid recipients with phone numbers.')
            else:
                try:
                    result = send_bulk_sms(phones, message)
                    if result.get('success'):
                        messages.success(request, f'Bulk SMS sent to {len(phones)} recipients.')
                    else:
                        messages.error(request, f'Failed: {result.get("message")}')
                except Exception as e:
                    messages.error(request, f'Error: {e}')

    return render(request, 'dashboard/bulk_sms.html', {
        'counts': counts,
        'classes': classes,
        'result': result,
    })


@login_required
def messages_inbox(request):
    """Each user sees messages sent to them."""
    from apps.notifications.models import MessageRecipient

    qs = MessageRecipient.objects.filter(
        recipient=request.user, is_archived=False
    ).select_related('message', 'message__sender', 'message__school').order_by('-message__created_at')

    unread_count = qs.filter(is_read=False).count()

    return render(request, 'dashboard/messages_inbox.html', {
        'messages': qs,
        'unread_count': unread_count,
    })


@login_required
def message_detail(request, recipient_id):
    """View a single message and mark it as read."""
    from apps.notifications.models import MessageRecipient

    msg_recipient = get_object_or_404(
        MessageRecipient, id=recipient_id, recipient=request.user
    )
    msg_recipient.mark_read()

    return render(request, 'dashboard/message_detail.html', {
        'recipient': msg_recipient,
        'message': msg_recipient.message,
    })


@login_required
def message_archive(request, recipient_id):
    """Archive a message (hide from inbox)."""
    from apps.notifications.models import MessageRecipient

    msg_recipient = get_object_or_404(
        MessageRecipient, id=recipient_id, recipient=request.user
    )
    msg_recipient.is_archived = True
    msg_recipient.save()
    messages.success(request, 'Message archived.')
    return redirect('messages_inbox')


@login_required
def compose_message(request):
    """School Admin composes a new message."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message, MessageRecipient
    from apps.accounts.models import User

    school = request.user.school

    # Count recipients for each group
    teachers = User.objects.filter(school=school, role='teacher', is_active=True)
    staff_users = User.objects.filter(school=school, role='accountant', is_active=True)
    class_teachers = User.objects.filter(
        school=school, role='teacher', is_active=True,
        teacher_profile__is_class_teacher=True
    )

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()
        priority = request.POST.get('priority', 'normal')
        category = request.POST.get('category', 'general')
        recipient_group = request.POST.get('recipient_group', 'teachers')
        specific_id = request.POST.get('specific_recipient', '').strip()

        errors = []
        if not subject:
            errors.append('Subject is required.')
        if not body:
            errors.append('Message body is required.')

        # Determine recipients
        recipients_qs = User.objects.none()

        if recipient_group == 'teachers':
            recipients_qs = teachers
        elif recipient_group == 'staff':
            recipients_qs = staff_users
        elif recipient_group == 'class_teachers':
            recipients_qs = class_teachers
        elif recipient_group == 'all':
            recipients_qs = User.objects.filter(
                school=school,
                role__in=['teacher', 'accountant'],
                is_active=True
            )
        elif recipient_group == 'specific' and specific_id:
            recipients_qs = User.objects.filter(
                id=specific_id, school=school, is_active=True
            )

        if not recipients_qs.exists():
            errors.append('No recipients found for the selected group.')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            # Create the message
            msg = Message.objects.create(
                school=school,
                sender=request.user,
                subject=subject,
                body=body,
                priority=priority,
                category=category,
            )

            # Create recipient rows
            recipient_count = 0
            for r in recipients_qs:
                MessageRecipient.objects.create(message=msg, recipient=r)
                recipient_count += 1

                # Also create in-app notification
                try:
                    from apps.notifications.models import Notification
                    Notification.objects.create(
                        recipient=r,
                        channel='in_app',
                        title=f'New message: {subject}',
                        message=body[:200],
                        is_read=False,
                    )
                except Exception:
                    pass

            messages.success(request, f'Message sent to {recipient_count} recipient(s).')
            return redirect('messages_sent')

    # Counts for display
    counts = {
        'teachers': teachers.count(),
        'staff': staff_users.count(),
        'class_teachers': class_teachers.count(),
        'all': User.objects.filter(
            school=school,
            role__in=['teacher', 'accountant'],
            is_active=True
        ).count(),
    }

    all_recipients = User.objects.filter(
        school=school,
        role__in=['teacher', 'accountant'],
        is_active=True,
    ).order_by('first_name', 'last_name')

    return render(request, 'dashboard/messages_compose.html', {
        'counts': counts,
        'all_recipients': all_recipients,
    })


@login_required
def messages_sent(request):
    """School Admin sees their sent messages."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message

    sent = Message.objects.filter(
        sender=request.user
    ).prefetch_related('recipients').order_by('-created_at')

    return render(request, 'dashboard/messages_sent.html', {
        'messages': sent,
    })


@login_required
def message_delete(request, message_id):
    """Sender can delete a message."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Message

    msg = get_object_or_404(Message, id=message_id, sender=request.user)
    msg.delete()
    messages.success(request, 'Message deleted.')
    return redirect('messages_sent')


@login_required
def admin_alerts_list(request):
    """List all alerts for the school admin."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Alert

    school = request.user.school
    qs = Alert.objects.filter(school=school).order_by('-created_at')

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter in ('new', 'reviewing', 'resolved', 'dismissed'):
        qs = qs.filter(status=status_filter)
    else:
        # Default: show unresolved
        qs = qs.filter(status__in=['new', 'reviewing'])

    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        qs = qs.filter(category=category_filter)

    # Counts
    all_alerts = Alert.objects.filter(school=school)
    counts = {
        'new': all_alerts.filter(status='new').count(),
        'reviewing': all_alerts.filter(status='reviewing').count(),
        'resolved': all_alerts.filter(status='resolved').count(),
        'dismissed': all_alerts.filter(status='dismissed').count(),
        'all': all_alerts.count(),
    }

    return render(request, 'dashboard/admin_alerts_list.html', {
        'alerts': qs[:200],
        'status_filter': status_filter or 'unresolved',
        'category_filter': category_filter,
        'counts': counts,
    })


@login_required
def admin_alert_resolve(request, alert_id):
    """Resolve or dismiss an alert."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.notifications.models import Alert

    alert = get_object_or_404(Alert, id=alert_id, school=request.user.school)

    if request.method == 'POST':
        action = request.POST.get('action', 'resolve')
        notes = request.POST.get('notes', '').strip()

        if action == 'dismiss':
            alert.dismiss(request.user, notes)
            messages.success(request, 'Alert dismissed.')
        else:
            alert.resolve(request.user, notes)
            messages.success(request, 'Alert resolved.')

    return redirect('admin_alerts_list')


