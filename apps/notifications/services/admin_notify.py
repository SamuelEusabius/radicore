"""
Helper to send notifications and emails to Super Admins.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


def notify_super_admins(title, message, send_email=True, email_html=None):
    """
    Notify all Super Admins via:
      - In-app notification (visible in the bell icon)
      - Email (to each super admin's email address)

    Args:
        title (str): Short title for the notification
        message (str): Full message body
        send_email (bool): Whether to also send an email
        email_html (str): Optional HTML body for the email

    Returns:
        dict: {'notifications_created': int, 'emails_sent': int}
    """
    from apps.accounts.models import User
    from ..models import Notification

    super_admins = User.objects.filter(role='super_admin', is_active=True)
    notifications_created = 0
    emails_sent = 0

    for admin in super_admins:
        # Create in-app notification
        try:
            Notification.objects.create(
                recipient=admin,
                channel='in_app',
                title=title,
                message=message,
                is_read=False,
            )
            notifications_created += 1
        except Exception as e:
            print(f"Failed to create notification for {admin.email}: {e}")

        # Send email
        if send_email and admin.email:
            try:
                if email_html:
                    send_mail(
                        subject=title,
                        message=message,  # plain text fallback
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin.email],
                        html_message=email_html,
                        fail_silently=True,
                    )
                else:
                    send_mail(
                        subject=title,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin.email],
                        fail_silently=True,
                    )
                emails_sent += 1
            except Exception as e:
                print(f"Failed to send email to {admin.email}: {e}")

    return {
        'notifications_created': notifications_created,
        'emails_sent': emails_sent,
    }


# ==========================================================
# TEMPLATES
# ==========================================================

def new_school_registered_email(school, admin_user):
    """Return (title, plain_message, html_message) for new school signup."""
    title = f"New School Registered: {school.name}"
    plain = f"""
New school registered on School MS

School: {school.name}
Code: {school.code or '—'}
Email: {school.email or '—'}
Plan: {school.plan.name if school.plan else 'None selected'}

Admin: {admin_user.get_full_name() or admin_user.email}
Admin Email: {admin_user.email}

Registered on: {timezone.now().strftime('%d %b %Y at %H:%M')}

Log in to view: /dashboard/schools/
""".strip()

    html = f"""
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a;">
  <div style="background: #00695c; color: white; padding: 20px;">
    <h1 style="margin: 0; font-size: 18px;">New School Registered</h1>
  </div>
  <div style="background: #ffffff; padding: 24px; border: 1px solid #e5e7eb;">
    <p style="font-size: 15px; color: #4b5563;">A new school has joined School MS.</p>

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px; width: 40%;">School Name</td>
        <td style="padding: 8px 0; font-weight: 600; font-size: 13px;">{school.name}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">School Code</td>
        <td style="padding: 8px 0; font-family: monospace; font-weight: 600; font-size: 13px;">{school.code or '—'}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">School Email</td>
        <td style="padding: 8px 0; font-size: 13px;">{school.email or '—'}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Plan</td>
        <td style="padding: 8px 0; font-size: 13px;">{school.plan.name if school.plan else 'None'}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Admin</td>
        <td style="padding: 8px 0; font-size: 13px;">{admin_user.get_full_name() or admin_user.email}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Registered</td>
        <td style="padding: 8px 0; font-size: 13px;">{timezone.now().strftime('%d %b %Y at %H:%M')}</td>
      </tr>
    </table>

    <a href="{settings.DEFAULT_FROM_EMAIL.split('@')[-1]}" style="display: inline-block; background: #ff6f00; color: white; padding: 12px 24px; text-decoration: none; font-weight: 600; font-size: 14px;">View in Dashboard</a>
  </div>
  <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 11px; color: #6b7280; border: 1px solid #e5e7eb; border-top: none;">
    This is an automated notification from School MS.
  </div>
</div>
"""
    return title, plain, html


def new_subscription_email(school, plan, payment_method):
    """Return (title, plain_message, html_message) for new subscription."""
    method_display = {
        'mpesa': 'M-Pesa',
        'bank': 'Bank Transfer',
        'cash': 'Cash',
    }.get(payment_method, payment_method or 'Not specified')

    title = f"New Subscription: {school.name} → {plan.name}"

    plain = f"""
New subscription on School MS

School: {school.name}
Code: {school.code or '—'}
Plan: {plan.name}
Price: KES {plan.price_kes}
Payment Method: {method_display}

Max Students: {plan.max_students}
Max Teachers: {plan.max_teachers}

Selected on: {timezone.now().strftime('%d %b %Y at %H:%M')}
""".strip()

    html = f"""
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #1a1a1a;">
  <div style="background: #00695c; color: white; padding: 20px;">
    <h1 style="margin: 0; font-size: 18px;">New Subscription Selected</h1>
  </div>
  <div style="background: #ffffff; padding: 24px; border: 1px solid #e5e7eb;">
    <p style="font-size: 15px; color: #4b5563;">A school has selected a subscription plan.</p>

    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px; width: 40%;">School</td>
        <td style="padding: 8px 0; font-weight: 600; font-size: 13px;">{school.name}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Plan</td>
        <td style="padding: 8px 0; font-weight: 600; font-size: 13px; color: #00695c;">{plan.name}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Price</td>
        <td style="padding: 8px 0; font-weight: 600; font-size: 13px;">KES {plan.price_kes}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Payment Method</td>
        <td style="padding: 8px 0; font-size: 13px;">{method_display}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Max Students</td>
        <td style="padding: 8px 0; font-size: 13px;">{plan.max_students}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Max Teachers</td>
        <td style="padding: 8px 0; font-size: 13px;">{plan.max_teachers}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280; font-size: 13px;">Time</td>
        <td style="padding: 8px 0; font-size: 13px;">{timezone.now().strftime('%d %b %Y at %H:%M')}</td>
      </tr>
    </table>

    <p style="font-size: 13px; color: #dc2626; background: #fef2f2; padding: 12px; border-left: 3px solid #dc2626;">
      <strong>Action needed:</strong> Follow up with the school to confirm payment.
    </p>
  </div>
  <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 11px; color: #6b7280; border: 1px solid #e5e7eb; border-top: none;">
    This is an automated notification from School MS.
  </div>
</div>
"""
    return title, plain, html