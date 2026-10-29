from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import School, SubscriptionPlan
from apps.accounts.models import User


def landing(request):
    return render(request, 'public/landing.html',
                  {'plans': SubscriptionPlan.objects.all()})


def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        school = request.POST.get('school', '').strip()
        message_body = request.POST.get('message', '').strip()

        if not name or not email or not message_body:
            messages.error(request, 'Please fill in all required fields.')
        else:
            # Send to your email
            try:
                send_mail(
                    subject=f'[School MS Contact] Message from {name}',
                    message=(
                        f"Name: {name}\n"
                        f"Email: {email}\n"
                        f"School: {school or '—'}\n\n"
                        f"Message:\n{message_body}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@schoolms.co.ke',
                    recipient_list=['samuelusabius14164@gmail.com'],
                    fail_silently=True,
                )
                messages.success(request, f'Thank you, {name}! Your message has been sent. We will reply to {email} shortly.')
            except Exception:
                messages.success(request, 'Your message was received. We will be in touch soon.')

            return redirect('/contact/')

    return render(request, 'public/contact.html')


def school_signup(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        plan_id = request.POST.get('plan')
        admin_email = request.POST.get('admin_email', '').strip()
        admin_password = request.POST.get('admin_password', '')

        if not name or not admin_email or not admin_password:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('school_signup')

        if School.objects.filter(name=name).exists():
            messages.error(request, f'A school named "{name}" already exists.')
            return redirect('school_signup')

        if User.objects.filter(email=admin_email).exists():
            messages.error(request, f'The email "{admin_email}" is already registered. Try another one.')
            return redirect('school_signup')

        plan = SubscriptionPlan.objects.filter(id=plan_id).first() if plan_id else None
        school = School.objects.create(name=name, email=email, plan=plan)

                # Create the school admin user
        admin_user = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            password=admin_password,
            role='principal',
            school=school,
        )

        # === Notify Super Admin about the new school ===
        try:
            from apps.notifications.services.admin_notify import (
                notify_super_admins, new_school_registered_email
            )
            title, plain, html = new_school_registered_email(school, admin_user)
            notify_super_admins(title, plain, send_email=True, email_html=html)
        except Exception as e:
            # Don't break signup if email fails
            print(f"Super Admin notification failed: {e}")

        messages.success(request, f'School "{name}" registered! Please log in.')
        return redirect('/accounts/login/')

    return render(request, 'public/signup.html',
                  {'plans': SubscriptionPlan.objects.all()})
    
def help_page(request):
    """Public help & support page."""
    return render(request, 'public/help.html')
def about(request):
    """Public Vision & Mission page."""
    return render(request, 'public/about.html')
def privacy(request):
    """Public Privacy Policy page."""
    return render(request, 'public/privacy.html')


def terms(request):
    """Public Terms & Conditions page."""
    return render(request, 'public/terms.html')
def resource_centre(request):
    """A polite placeholder for the upcoming Digital Resource Centre."""
    return render(request, 'public/resource_centre.html')

def testimonials(request):
    """A page showing feedback from schools using RacodCore."""
    return render(request, 'public/testimonials.html')