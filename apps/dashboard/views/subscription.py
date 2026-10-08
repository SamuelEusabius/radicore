"""
Subscription views:
- Plan display and selection
- Subscription management (school admin)
- Super admin subscription management
- Payment flow
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta

from apps.schools.models import SubscriptionPlan, SchoolSubscription, School


@login_required
def subscription_view(request):
    """Subscription page — accessible only to Super Admin and School Admin."""
    user = request.user

    if user.role not in ('super_admin', 'principal'):
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from apps.schools.models import School, SubscriptionPlan, SchoolSubscription
    from django.utils import timezone
    from datetime import timedelta

    all_schools = School.objects.all().order_by('name') if user.role == 'super_admin' else School.objects.none()
    school = user.school if user.role == 'principal' else None

    if user.role == 'super_admin':
        school_id = request.GET.get('school')
        if school_id:
            try:
                school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                school = None

    plans = SubscriptionPlan.objects.all().order_by('order', 'min_students')

    # Get or create subscription
    subscription = None
    if school:
        subscription, created = SchoolSubscription.objects.get_or_create(
    school=school,
    defaults={
        'status': SchoolSubscription.Status.TRIAL,
        'trial_ends_at': timezone.now() + timedelta(days=14),
    }
)

    # Compute pricing previews for each plan × cycle
    pricing_matrix = {}
    for plan in plans:
        pricing_matrix[plan.id] = {
            'monthly': SchoolSubscription.calculate_price(plan, 'monthly'),
            'term':    SchoolSubscription.calculate_price(plan, 'term'),
            'contract_1y': SchoolSubscription.calculate_price(plan, 'contract', 1),
            'contract_2y': SchoolSubscription.calculate_price(plan, 'contract', 2),
            'contract_3y': SchoolSubscription.calculate_price(plan, 'contract', 3),
            'contract_5y': SchoolSubscription.calculate_price(plan, 'contract', 5),
        }

    # Handle POST — plan selection
    if request.method == 'POST' and school:
        plan_id = request.POST.get('plan_id')
        billing_cycle = request.POST.get('billing_cycle', 'term')
        contract_years = request.POST.get('contract_years', '1')
        payment_method = request.POST.get('payment_method')
        terms_accepted = request.POST.get('terms_accepted')

        try:
            contract_years = int(contract_years)
        except ValueError:
            contract_years = 1

        if not terms_accepted:
            messages.error(request, 'You must accept the Terms & Conditions to continue.')
        elif not plan_id:
            messages.error(request, 'Please select a plan.')
        elif not payment_method:
            messages.error(request, 'Please select a payment method.')
        else:
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)

                total, duration_days, savings = SchoolSubscription.calculate_price(
                    plan, billing_cycle, contract_years
                )
                subscription.plan = plan
                subscription.billing_cycle = billing_cycle
                subscription.contract_years = contract_years if billing_cycle == 'contract' else 0
                subscription.max_students = plan.max_students
                subscription.max_teachers = plan.max_teachers
                subscription.last_payment_method = payment_method
                subscription.total_paid_kes = total
                # Do NOT set paid_until yet — waiting for Super Admin confirmation
                # Do NOT set status to ACTIVE yet
                subscription.status = SchoolSubscription.Status.PENDING_PAYMENT
                subscription.save()
                
                                # === Notify Super Admin about pending payment ===
                try:
                    from apps.notifications.services.admin_notify import (
                        notify_super_admins, new_subscription_email
                    )
                    title, plain, html = new_subscription_email(
                        school=school,
                        plan=plan,
                        payment_method=payment_method,
                    )
                    notify_super_admins(
                        f"[PENDING] {title}",
                        f"Payment pending confirmation for {school.name}.\n\n{plain}",
                        send_email=True,
                        email_html=html,
                    )
                except Exception as e:
                    print(f"Notification failed: {e}")

                # Redirect to payment instructions page
                return redirect('subscription_payment_pending', school_id=school.id)

                # === Notify Super Admin ===
                try:
                    from apps.notifications.services.admin_notify import (
                        notify_super_admins, new_subscription_email
                    )
                    title, plain, html = new_subscription_email(
                        school=school,
                        plan=plan,
                        payment_method=payment_method,
                    )
                    notify_super_admins(title, plain, send_email=True, email_html=html)
                except Exception as e:
                    print(f"Super Admin notification failed: {e}")

                if payment_method == 'mpesa':
                    messages.success(
                        request,
                        f'Plan selected: {plan.name} ({subscription.billing_cycle_display}). '
                        f'Total: KES {total:,.0f}. You will receive an M-Pesa prompt shortly.'
                    )
                else:
                    messages.success(
                        request,
                        f'Plan selected: {plan.name} ({subscription.billing_cycle_display}). '
                        f'Total: KES {total:,.0f}. Please transfer the amount to our bank account.'
                    )

                return redirect('subscription_view')

            except SubscriptionPlan.DoesNotExist:
                messages.error(request, 'Invalid plan selected.')

    return render(request, 'dashboard/subscription.html', {
        'school': school,
        'schools': all_schools,
        'plans': plans,
        'subscription': subscription,
        'pricing_matrix': pricing_matrix,
        'is_super_admin': user.role == 'super_admin',
    })


@login_required
def subscription_edit_admin(request, school_id):
    """Super Admin directly edits a school's subscription."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from apps.schools.models import School, SubscriptionPlan, SchoolSubscription
    from django.utils import timezone
    from datetime import timedelta


    school = get_object_or_404(School, id=school_id)

    # Get or create subscription
    subscription, _ = SchoolSubscription.objects.get_or_create(
        school=school,
        defaults={
            'status': SchoolSubscription.Status.TRIAL,
            'trial_ends_at': timezone.now() + timedelta(days=14),
        }
    )

    plans = SubscriptionPlan.objects.all().order_by('order', 'min_students')
    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        # ---------- RESET TRIAL ----------
        if action == 'reset_trial':
            subscription.status = SchoolSubscription.Status.TRIAL
            subscription.trial_started_at = timezone.now()
            subscription.trial_ends_at = timezone.now() + timedelta(days=14)
            subscription.paid_until = None
            subscription.save()
            messages.success(request, f'14-day trial reset for {school.name}.')
        # ---------- CANCEL ----------
        if action == 'cancel':
            subscription.status = SchoolSubscription.Status.CANCELLED
            subscription.save()
            messages.warning(request, f'Subscription cancelled for {school.name}.')
            return redirect('subscription_edit_admin', school_id=school.id)

        # ---------- ACTIVATE ----------
        if action == 'activate':
            subscription.status = SchoolSubscription.Status.ACTIVE
            subscription.save()
            messages.success(request, f'Subscription activated for {school.name}.')
            return redirect('subscription_edit_admin', school_id=school.id)

        # ---------- SAVE (main update) ----------
        plan_id = request.POST.get('plan')
        billing_cycle = request.POST.get('billing_cycle', 'term')
        contract_years = request.POST.get('contract_years', '0')
        status = request.POST.get('status', 'active')
        max_students = request.POST.get('max_students', '')
        max_teachers = request.POST.get('max_teachers', '')
        paid_until_str = request.POST.get('paid_until', '')
        payment_method = request.POST.get('last_payment_method', '')
        payment_reference = request.POST.get('last_payment_reference', '')
        total_paid = request.POST.get('total_paid_kes', '0')

        try:
            contract_years = int(contract_years) if contract_years else 0
        except ValueError:
            contract_years = 0

        if plan_id:
            subscription.plan = SubscriptionPlan.objects.filter(id=plan_id).first()

        subscription.billing_cycle = billing_cycle
        subscription.contract_years = contract_years if billing_cycle == 'contract' else 0
        subscription.status = status
        subscription.last_payment_method = payment_method
        subscription.last_payment_reference = payment_reference

        try:
            subscription.total_paid_kes = float(total_paid or 0)
        except ValueError:
            subscription.total_paid_kes = 0

        if max_students:
            try:
                subscription.max_students = int(max_students)
            except ValueError:
                pass

        if max_teachers:
            try:
                subscription.max_teachers = int(max_teachers)
            except ValueError:
                pass

        if paid_until_str:
            try:
                from datetime import datetime
                subscription.paid_until = timezone.make_aware(
                    datetime.strptime(paid_until_str, '%Y-%m-%d')
                )
            except (ValueError, TypeError):
                pass

        subscription.save()
        messages.success(request, f'Subscription updated for {school.name}.')
        return redirect('subscription_edit_admin', school_id=school.id)

    # ---- Compute trial-end / paid-until as ISO date for the form ----
    paid_until_iso = ''
    if subscription.paid_until:
        paid_until_iso = subscription.paid_until.strftime('%Y-%m-%d')

    trial_ends_iso = ''
    if subscription.trial_ends_at:
        trial_ends_iso = subscription.trial_ends_at.strftime('%Y-%m-%d')

    return render(request, 'dashboard/subscription_edit_admin.html', {
        'school': school,
        'subscription': subscription,
        'plans': plans,
        'billing_cycles': SchoolSubscription.BillingCycle.choices,
        'statuses': SchoolSubscription.Status.choices,
        'payment_methods': SchoolSubscription.PaymentMethod.choices,
        'paid_until_iso': paid_until_iso,
        'trial_ends_iso': trial_ends_iso,
    })


@login_required
def subscription_admin_picker(request):
    """Super Admin — school picker for subscription management."""
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription

    schools = School.objects.all().order_by('name')

    # Attach current subscription info to each school
    school_rows = []
    for s in schools:
        sub = SchoolSubscription.objects.filter(school=s).select_related('plan').first()
        student_count = s.students.count() if hasattr(s, 'students') else 0
        school_rows.append({
            'school': s,
            'subscription': sub,
            'student_count': student_count,
        })

    return render(request, 'dashboard/subscription_admin_picker.html', {
        'school_rows': school_rows,
        'total_schools': schools.count(),
    })


@login_required
def subscription_payment_pending(request, school_id):
    """Show payment instructions after school admin selects method."""
    from apps.schools.models import School, SchoolSubscription

    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    school = get_object_or_404(School, id=school_id)

    # Security — school admins only see their own school
    if request.user.role == 'principal' and request.user.school != school:
        return redirect('dashboard_home')

    try:
        subscription = SchoolSubscription.objects.get(school=school)
    except SchoolSubscription.DoesNotExist:
        messages.error(request, 'No subscription found for this school.')
        return redirect('subscription_view')

    # Generate a reference number for this payment
    import random
    import string
    reference = f"SUB-{school.code or school.id}-{''.join(random.choices(string.digits, k=6))}"

    # Save the reference
    subscription.last_payment_reference = reference
    subscription.save(update_fields=['last_payment_reference'])

    return render(request, 'dashboard/subscription_payment_pending.html', {
        'school': school,
        'subscription': subscription,
        'reference': reference,
    })


@login_required
def subscription_payment_status(request, school_id):
    """Check the current status of the subscription payment."""
    from apps.schools.models import School, SchoolSubscription

    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    school = get_object_or_404(School, id=school_id)

    if request.user.role == 'principal' and request.user.school != school:
        return redirect('dashboard_home')

    try:
        subscription = SchoolSubscription.objects.get(school=school)
    except SchoolSubscription.DoesNotExist:
        return redirect('subscription_view')

    return render(request, 'dashboard/subscription_payment_status.html', {
        'school': school,
        'subscription': subscription,
    })


@login_required
def confirm_subscription_payment(request, school_id):
    """Super Admin confirms a pending payment, activating the subscription."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription
    from django.utils import timezone
    from datetime import timedelta
    from apps.notifications.models import Notification
    from django.core.mail import send_mail
    from django.conf import settings

    school = get_object_or_404(School, id=school_id)

    try:
        subscription = SchoolSubscription.objects.get(school=school)
    except SchoolSubscription.DoesNotExist:
        messages.error(request, 'No subscription found.')
        return redirect('schools_manage')

    if request.method == 'POST':
        # Compute duration based on billing cycle
        if subscription.billing_cycle == 'monthly':
            duration_days = 30
        elif subscription.billing_cycle == 'term':
            duration_days = 90
        elif subscription.billing_cycle == 'contract':
            duration_days = 365 * max(subscription.contract_years, 1)
        else:
            duration_days = 90

        subscription.status = SchoolSubscription.Status.ACTIVE
        subscription.paid_until = timezone.now() + timedelta(days=duration_days)
        subscription.last_payment_date = timezone.now()
        subscription.payment_confirmed_by = request.user
        subscription.payment_confirmed_at = timezone.now()
        subscription.payment_notes = request.POST.get('payment_notes', '').strip()
        subscription.save()

        # Notify school admin
        try:
            school_admins = school.users.filter(role='principal')
            for admin in school_admins:
                Notification.objects.create(
                    recipient=admin,
                    channel='in_app',
                    title='Payment Confirmed',
                    message=f'Your subscription for {school.name} is now ACTIVE until {subscription.paid_until.strftime("%d %b %Y")}.',
                )
                if admin.email:
                    send_mail(
                        subject='Subscription Activated — School MS',
                        message=f"""
Hello {admin.get_full_name() or admin.email},

Your subscription for {school.name} has been confirmed.

Plan: {subscription.plan.name if subscription.plan else 'N/A'}
Billing: {subscription.billing_cycle_display}
Paid Until: {subscription.paid_until.strftime('%d %b %Y')}
Reference: {subscription.last_payment_reference or '—'}

Thank you for using School MS.

— The School MS Team
""".strip(),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin.email],
                        fail_silently=True,
                    )
        except Exception as e:
            print(f"Failed to notify admin: {e}")

        messages.success(request, f'✅ Payment confirmed. Subscription for {school.name} is now ACTIVE until {subscription.paid_until.strftime("%d %b %Y")}.')
        return redirect('schools_manage')

    return render(request, 'dashboard/confirm_subscription_payment.html', {
        'school': school,
        'subscription': subscription,
    })


@login_required
def subscription_plans(request):
    """Redesigned subscription page with tier-based pricing."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.schools.models import SubscriptionPlan, SchoolSubscription, School
    from apps.students.models import Student
    from django.utils import timezone

    school = request.user.school
    if not school:
        messages.error(request, 'No school linked to your account.')
        return redirect('dashboard_home')

    # Current subscription
    subscription = SchoolSubscription.objects.filter(school=school).select_related('plan').first()

    # Student count → determines the tier
    student_count = Student.objects.filter(school=school, is_active=True).count()

    # All active plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('order', 'min_students')

    # Highlight the plan matching this school's student count
    matched_plan_id = None
    for plan in plans:
        if plan.matches_student_count(student_count):
            matched_plan_id = plan.id
            break

    # Trial status
    is_trial = False
    days_left = 0
    trial_end = None
    if subscription and subscription.status == 'trial' and subscription.trial_ends_at:
        is_trial = subscription.trial_ends_at > timezone.now()
        days_left = max(0, (subscription.trial_ends_at - timezone.now()).days)
        trial_end = subscription.trial_ends_at

    # Current plan
    current_plan = subscription.plan if subscription else None

    return render(request, 'dashboard/subscription_plans.html', {
        'plans': plans,
        'student_count': student_count,
        'matched_plan_id': matched_plan_id,
        'subscription': subscription,
        'current_plan': current_plan,
        'is_trial': is_trial,
        'days_left': days_left,
        'trial_end': trial_end,
        'trial_student_cap': 450,
    })


@login_required
def subscription_confirm(request):
    """Handle subscription plan selection + payment."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    if request.method != 'POST':
        return redirect('subscription_plans')

    from apps.schools.models import SubscriptionPlan, SchoolSubscription
    from django.utils import timezone
    from datetime import timedelta

    school = request.user.school
    plan_id = request.POST.get('plan_id')
    cycle = request.POST.get('cycle', 'term')
    agreed = request.POST.get('agree_terms') == 'on'

    if not agreed:
        messages.error(request, 'You must agree to the Terms & Conditions to continue.')
        return redirect('subscription_plans')

    try:
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        messages.error(request, 'Invalid plan selected.')
        return redirect('subscription_plans')

    # Determine duration in days
    duration_days = {
        'monthly': 30,
        'term': 90,
        'contract_1y': 365,
        'contract_2y': 730,
    }.get(cycle, 90)

    # Price
    price = plan.price_for_cycle(cycle)

    # Update or create subscription
    subscription, created = SchoolSubscription.objects.get_or_create(
        school=school,
        defaults={
            'plan': plan,
            'status': 'pending_payment',
            'billing_cycle': 'term' if cycle in ('term', 'contract_1y', 'contract_2y') else 'monthly',
            'total_paid_kes': price,
        }
    )
    if not created:
        subscription.plan = plan
        subscription.status = 'pending_payment'
        subscription.total_paid_kes = price
        subscription.billing_cycle = (
            'term' if cycle in ('term', 'contract_1y', 'contract_2y') else 'monthly'
        )
        subscription.save()

    # Store intent for the payment page
    request.session['pending_subscription'] = {
        'plan_id': plan.id,
        'plan_name': plan.name,
        'cycle': cycle,
        'price': float(price),
        'duration_days': duration_days,
    }

    messages.success(
        request,
        f'Plan "{plan.name}" selected for {cycle.replace("_", " ")}. '
        f'Please complete payment.'
    )
    return redirect('subscription_payment')


@login_required
def subscription_payment(request):
    """Payment page after plan selection."""
    if request.user.role not in ('principal', 'super_admin'):
        return redirect('dashboard_home')

    pending = request.session.get('pending_subscription')
    if not pending:
        messages.error(request, 'No pending subscription. Please choose a plan.')
        return redirect('subscription_plans')

    return render(request, 'dashboard/subscription_payment.html', {
        'pending': pending,
    })


