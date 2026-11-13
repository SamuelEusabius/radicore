from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.notifications.models import PlatformSMSConfig, SchoolSmsConfig, SMSMessageLog
from apps.notifications.at_service import send_sms, fetch_balance


@login_required
def super_admin_sms_settings(request):
    """Super Admin configures platform-wide Africa's Talking credentials."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    config, _ = PlatformSMSConfig.objects.get_or_create(id=1)

    if request.method == 'POST':
        config.username = request.POST.get('username', '').strip()
        config.api_key = request.POST.get('api_key', '').strip()
        config.sender_id = request.POST.get('sender_id', 'RacodCore').strip()
        config.is_active = request.POST.get('is_active') == 'on'
        config.save()
        messages.success(request, 'Platform SMS settings saved.')
        return redirect('super_admin_sms_settings')

    # Fetch live balance if config exists
    balance = None
    if config.username and config.api_key:
        balance = fetch_balance(school=None)

    return render(request, 'dashboard/super_admin_sms_settings.html', {
        'config': config,
        'balance': balance,
    })


@login_required
def school_sms_settings(request):
    """School admin (Principal/Accountant) configures their own AT credentials."""
    if request.user.role not in ('principal', 'accountant', 'super_admin'):
        return redirect('dashboard_home')

    school = request.user.school
    config, _ = SchoolSmsConfig.objects.get_or_create(
        school=school,
        defaults={'username': '', 'api_key': '', 'sender_id': 'SCHOOL'}
    )

    if request.method == 'POST':
        config.username = request.POST.get('username', '').strip()
        config.api_key = request.POST.get('api_key', '').strip()
        config.sender_id = request.POST.get('sender_id', '').strip()
        config.is_active = request.POST.get('is_active') == 'on'
        config.save()
        messages.success(request, 'School SMS settings saved.')
        return redirect('school_sms_settings')

    balance = None
    if config.username and config.api_key:
        balance = fetch_balance(school=school)

    return render(request, 'dashboard/school_sms_settings.html', {
        'config': config,
        'balance': balance,
    })


@login_required
def test_sms(request):
    """Test send an SMS to the logged-in user's phone (or a specified number)."""
    if request.method != 'POST':
        return redirect('dashboard_home')

    phone = request.POST.get('phone', '').strip()
    message = request.POST.get('message', 'This is a test SMS from RacodCore.').strip()

    if not phone:
        messages.error(request, 'Please provide a phone number.')
        return redirect(request.META.get('HTTP_REFERER', 'dashboard_home'))

    success, status = send_sms(
        school=request.user.school,
        phone_number=phone,
        message=message,
        user=request.user,
    )

    if success:
        messages.success(request, f'SMS sent to {phone}. Status: {status}')
    else:
        messages.error(request, f'SMS failed: {status}')

    return redirect(request.META.get('HTTP_REFERER', 'dashboard_home'))


@login_required
def sms_log(request):
    """View SMS delivery history (audit log)."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    logs = SMSMessageLog.objects.all()
    if request.user.role != 'super_admin':
        logs = logs.filter(school=request.user.school)

    logs = logs.order_by('-created_at')[:100]

    return render(request, 'dashboard/sms_log.html', {'logs': logs})