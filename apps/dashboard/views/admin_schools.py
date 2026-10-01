"""
Admin & Schools views (Super Admin scope):
- Super admin dashboard
- School management (CRUD, toggle active, logo, admin password)
- Board members
- User management (list, create)
- Cross-tenant student detail
- Platform performance
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.accounts.decorators import (
    role_required, super_admin_only,
)

User = get_user_model()


@login_required
def super_admin_dash(request):
    if request.user.role != 'super_admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription
    return render(request, 'dashboard/super_admin.html', {
        'school_count': School.objects.count(),
        'active_count': School.objects.filter(is_active=True).count(),
        'inactive_count': School.objects.filter(is_active=False).count(),
        'pending_payments': SchoolSubscription.objects.filter(
            status='pending_payment'
        ).select_related('school', 'plan'),
    })


@login_required
def manage_users(request):
    """List users with filters, search, and role breakdown."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.accounts.models import User
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    # ---------- Base queryset ----------
    if request.user.role == 'super_admin':
        base_qs = User.objects.all().select_related('school')
    else:
        base_qs = User.objects.filter(school=request.user.school)

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs.order_by('role', 'email')

    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )

    if role_filter:
        qs = qs.filter(role=role_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # ---------- Stats (unfiltered) ----------
    stats = {
        'total': base_qs.count(),
        'teachers': base_qs.filter(role='teacher').count(),
        'school_admins': base_qs.filter(role='school_admin').count(),
        'accountants': base_qs.filter(role='accountant').count(),
        'parents': base_qs.filter(role='parent').count(),
        'students': base_qs.filter(role='student').count(),
        'staff': base_qs.filter(role='staff').count(),
        'super_admins': base_qs.filter(role='super_admin').count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # ---------- Role choices ----------
    from apps.accounts.models import User as U
    role_choices = list(U.Role.choices)
    if request.user.role != 'super_admin':
        ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')
        role_choices = [(v, l) for v, l in role_choices if v in ALLOWED_FOR_SCHOOL_ADMIN]

    return render(request, 'dashboard/manage_users.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': role_choices,
        'total_filtered': qs.count(),
        'is_super_admin': request.user.role == 'super_admin',
    })


@login_required
def create_user(request):
    """Create a new user."""
    if not request.user.is_authenticated:
        return redirect('/accounts/login/')

    if getattr(request.user, 'role', None) not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    ALLOWED_FOR_SCHOOL_ADMIN = ('teacher', 'accountant', 'staff', 'parent', 'student')

    import secrets
    import string

    def generate_password(length=10):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    generated_password = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        # If user clicked "Generate" — auto-create password
        if request.POST.get('auto_password') == '1' or not password:
            password = generate_password()
            generated_password = password

        # Server-side role guard
        if not email or not role:
            messages.error(request, 'Email and role are required.')
        elif request.user.role != 'super_admin' and role not in ALLOWED_FOR_SCHOOL_ADMIN:
            messages.error(
                request,
                f'You are not allowed to create a "{role.replace("_", " ").title()}" account.'
            )
        elif User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" is already registered.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            # School assignment
            if request.user.role == 'super_admin':
                school_id = request.POST.get('school_id')
                if school_id:
                    from apps.schools.models import School
                    assigned_school = School.objects.filter(id=school_id).first() or request.user.school
                else:
                    assigned_school = request.user.school
            else:
                assigned_school = request.user.school

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                school=assigned_school,
            )
            messages.success(
                request,
                f'{role.replace("_", " ").title()} "{email}" created successfully.'
            )

            if generated_password:
                messages.info(
                    request,
                    f'Auto-generated password: {generated_password} — share this with the user securely.'
                )

            return redirect('manage_users')

    # Role choices
    if request.user.role == 'super_admin':
        role_choices = [r for r in User.Role.choices if r[0] != 'super_admin']
    else:
        role_choices = [r for r in User.Role.choices if r[0] in ALLOWED_FOR_SCHOOL_ADMIN]

    schools = None
    if request.user.role == 'super_admin':
        from apps.schools.models import School
        schools = School.objects.filter(is_active=True).order_by('name')

    return render(request, 'dashboard/create_user.html', {
        'roles': role_choices,
        'schools': schools,
    })


@login_required
def schools_manage(request):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    from django.db import models

    schools = School.objects.all().order_by('name')

    search = request.GET.get('q', '').strip()
    if search:
        schools = schools.filter(
            models.Q(name__icontains=search) |
            models.Q(code__icontains=search) |
            models.Q(nemis_code__icontains=search) |
            models.Q(county__icontains=search)
        )

    return render(request, 'dashboard/schools_manage.html', {
        'schools': schools,
        'search': search,
        'total': schools.count(),
    })


@login_required
def school_add(request):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        county = request.POST.get('county', '').strip()
        sub_county = request.POST.get('sub_county', '').strip()
        nemis_code = request.POST.get('nemis_code', '').strip()
        school_type = request.POST.get('school_type', 'private')
        gender = request.POST.get('gender', 'mixed')
        level = request.POST.get('level', 'all')
        motto = request.POST.get('motto', '').strip()
        physical_address = request.POST.get('physical_address', '').strip()
        blocked_message = request.POST.get('blocked_message', '').strip()

        admin_email = request.POST.get('admin_email', '').strip()
        admin_password = request.POST.get('admin_password', '').strip()
        admin_first_name = request.POST.get('admin_first_name', '').strip()
        admin_last_name = request.POST.get('admin_last_name', '').strip()

        errors = []
        if not name:
            errors.append('School name is required.')
        if not admin_email:
            errors.append('Admin email is required.')
        if not admin_password:
            errors.append('Admin password is required.')
        if School.objects.filter(name=name).exists():
            errors.append(f'A school named "{name}" already exists.')
        if User.objects.filter(email=admin_email).exists():
            errors.append(f'Email "{admin_email}" is already registered.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/school_add.html', {'form_data': request.POST})

        school = School.objects.create(
            name=name, email=email, phone=phone,
            county=county, sub_county=sub_county, nemis_code=nemis_code,
            school_type=school_type, gender=gender, level=level,
            motto=motto, physical_address=physical_address,
            blocked_message=blocked_message or None,
            is_active=True,
        )

        User.objects.create_user(
            username=admin_email, email=admin_email, password=admin_password,
            first_name=admin_first_name, last_name=admin_last_name,
            role='school_admin', school=school,
        )

        messages.success(request, f'School "{school.name}" created with code {school.code}.')
        return redirect('schools_manage')

    return render(request, 'dashboard/school_add.html')


@login_required
def school_toggle_active(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        school.is_active = not school.is_active
        school.save()
        status = 'activated' if school.is_active else 'deactivated'
        messages.success(request, f'{school.name} has been {status}.')
    return redirect('schools_manage')


@login_required
def school_change_admin_password(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)
    admins = User.objects.filter(school=school, role='school_admin')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_password = request.POST.get('new_password', '').strip()

        if not user_id or not new_password:
            messages.error(request, 'Select an admin and enter a new password.')
        elif len(new_password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        else:
            try:
                admin = admins.get(id=user_id)
                admin.set_password(new_password)
                admin.save()
                messages.success(request, f'Password changed for {admin.email}.')
                return redirect('schools_manage')
            except User.DoesNotExist:
                messages.error(request, 'Admin not found.')

    return render(request, 'dashboard/school_change_password.html', {
        'school': school, 'admins': admins,
    })


@login_required
def school_delete(request, school_id):
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        name = school.name
        school.delete()
        messages.success(request, f'School "{name}" has been permanently deleted.')
        return redirect('schools_manage')

    return render(request, 'dashboard/school_delete.html', {'school': school})


@login_required
def school_edit(request, school_id):
    """Super Admin edits school details + uploads logo."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, SubscriptionPlan, BoardMember

    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        # ---------- Basic info ----------
        school.name = request.POST.get('name', '').strip() or school.name
        school.email = request.POST.get('email', '').strip()
        school.phone = request.POST.get('phone', '').strip()
        school.motto = request.POST.get('motto', '').strip()
        school.county = request.POST.get('county', '').strip()
        school.sub_county = request.POST.get('sub_county', '').strip()
        school.ward = request.POST.get('ward', '').strip()
        school.physical_address = request.POST.get('physical_address', '').strip()
        school.postal_address = request.POST.get('postal_address', '').strip()
        school.nemis_code = request.POST.get('nemis_code', '').strip()

        # ---------- Classification ----------
        school.school_type = request.POST.get('school_type', 'private')
        school.gender = request.POST.get('gender', 'mixed')
        school.level = request.POST.get('level', 'all')

        # ---------- Status ----------
        school.is_active = request.POST.get('is_active') == 'on'

        # ---------- Subscription ----------
        plan_id = request.POST.get('plan')
        if plan_id:
            school.plan = SubscriptionPlan.objects.filter(id=plan_id).first()

        # ---------- Leadership ----------
        school.principal_name = request.POST.get('principal_name', '').strip()
        school.principal_id = request.POST.get('principal_id', '').strip()
        school.principal_phone = request.POST.get('principal_phone', '').strip()
        school.principal_email = request.POST.get('principal_email', '').strip()

        school.deputy_name = request.POST.get('deputy_name', '').strip()
        school.deputy_id = request.POST.get('deputy_id', '').strip()
        school.deputy_phone = request.POST.get('deputy_phone', '').strip()
        school.deputy_email = request.POST.get('deputy_email', '').strip()

        school.senior_teacher_name = request.POST.get('senior_teacher_name', '').strip()
        school.senior_teacher_id = request.POST.get('senior_teacher_id', '').strip()
        school.senior_teacher_phone = request.POST.get('senior_teacher_phone', '').strip()
        school.senior_teacher_email = request.POST.get('senior_teacher_email', '').strip()

        school.accountant_name = request.POST.get('accountant_name', '').strip()
        school.accountant_id = request.POST.get('accountant_id', '').strip()
        school.accountant_phone = request.POST.get('accountant_phone', '').strip()
        school.accountant_email = request.POST.get('accountant_email', '').strip()

        # ---------- Logo upload ----------
        if 'logo' in request.FILES:
            school.logo = request.FILES['logo']

        # ---------- Leadership photos ----------
        if 'principal_photo' in request.FILES:
            school.principal_photo = request.FILES['principal_photo']
        if 'deputy_photo' in request.FILES:
            school.deputy_photo = request.FILES['deputy_photo']
        if 'senior_teacher_photo' in request.FILES:
            school.senior_teacher_photo = request.FILES['senior_teacher_photo']
        if 'accountant_photo' in request.FILES:
            school.accountant_photo = request.FILES['accountant_photo']

        # ---------- Remove logo ----------
        if request.POST.get('remove_logo') == 'on':
            school.logo.delete(save=False)
            school.logo = None

        school.save()
        messages.success(request, f'✅ School "{school.name}" updated successfully.')
        return redirect('schools_manage')

    # GET — show form
    plans = SubscriptionPlan.objects.all().order_by('order', 'min_students')
    board_members = school.board_members.all()

    return render(request, 'dashboard/school_edit.html', {
        'school': school,
        'plans': plans,
        'board_members': board_members,
    })


@login_required
def school_remove_logo(request, school_id):
    """Quick action to remove a school's logo."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School
    school = get_object_or_404(School, id=school_id)
    school.logo.delete(save=False)
    school.logo = None
    school.save()
    messages.success(request, f'Logo removed for {school.name}.')
    return redirect('school_edit', school_id=school.id)


@login_required
def board_member_add(request, school_id):
    """Add a board member to a school."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, BoardMember
    school = get_object_or_404(School, id=school_id)

    if request.method == 'POST':
        BoardMember.objects.create(
            school=school,
            full_name=request.POST.get('full_name', '').strip(),
            id_number=request.POST.get('id_number', '').strip(),
            occupation=request.POST.get('occupation', '').strip(),
            role=request.POST.get('role', 'member'),
            phone=request.POST.get('phone', '').strip(),
            email=request.POST.get('email', '').strip(),
            photo=request.FILES.get('photo'),
        )
        messages.success(request, 'Board member added.')
        return redirect('school_edit', school_id=school.id)

    return render(request, 'dashboard/board_member_form.html', {
        'school': school,
        'roles': BoardMember.Role.choices,
    })


@login_required
def board_member_delete(request, member_id):
    """Delete a board member."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import BoardMember
    member = get_object_or_404(BoardMember, id=member_id)
    school_id = member.school.id
    member.delete()
    messages.success(request, 'Board member removed.')
    return redirect('school_edit', school_id=school_id)


@login_required
def super_admin_performance(request):
    """Show platform-wide performance metrics for the last 3 months."""
    if request.user.role != 'super_admin':
        return redirect('dashboard_home')

    from apps.schools.models import School, SchoolSubscription
    from apps.accounts.models import User
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.parents.models import Parent
    from apps.staff.models import NonTeachingStaff
    from apps.finance.models import Payment, Invoice
    from apps.notifications.models import Alert
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncMonth

    now = timezone.now()
    three_months_ago = now - timedelta(days=90)

    # ---------- OVERALL TOTALS ----------
    total_schools = School.objects.count()
    active_schools = School.objects.filter(is_active=True).count()
    total_users = User.objects.count()
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_parents = Parent.objects.count()
    total_staff = NonTeachingStaff.objects.filter(is_active=True).count()

    # ---------- 3-MONTH METRICS ----------
    # Schools registered in last 3 months
    schools_3m = School.objects.filter(created_at__gte=three_months_ago).count()

    # Users registered in last 3 months
    users_3m = User.objects.filter(date_joined__gte=three_months_ago).count()

    # Payments (fees collected) in last 3 months
    payments_3m = Payment.objects.filter(
        paid_at__gte=three_months_ago
    ).aggregate(total=Sum('amount_kes'))['total'] or 0

    # Invoices created in last 3 months
    invoices_3m = Invoice.objects.filter(
        created_at__gte=three_months_ago
    ).aggregate(total=Sum('amount_due'))['total'] or 0

    # Alerts in last 3 months
    alerts_3m = Alert.objects.filter(created_at__gte=three_months_ago).count()
    critical_alerts = Alert.objects.filter(
        created_at__gte=three_months_ago,
        severity='critical',
        status='new'
    ).count()

    # ---------- MONTHLY BREAKDOWN ----------
    monthly_schools = (
        School.objects.filter(created_at__gte=three_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    monthly_users = (
        User.objects.filter(date_joined__gte=three_months_ago)
        .annotate(month=TruncMonth('date_joined'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    monthly_payments = (
        Payment.objects.filter(paid_at__gte=three_months_ago)
        .annotate(month=TruncMonth('paid_at'))
        .values('month')
        .annotate(total=Sum('amount_kes'))
        .order_by('month')
    )

    # ---------- PERFORMANCE SCORES ----------
    # 4 service performance indicators (0-100%)

    # 1. School activation rate (active / total)
    activation_rate = round((active_schools / total_schools * 100), 1) if total_schools else 0

    # 2. Data richness (avg students per active school)
    avg_students_per_school = round(total_students / active_schools, 1) if active_schools else 0
    # Score: students per school relative to target of 200
    student_score = min(round((avg_students_per_school / 200) * 100, 1), 100)

    # 3. Financial activity (collections / expected invoices)
    financial_score = round((float(payments_3m) / float(invoices_3m) * 100), 1) if invoices_3m else 0
    financial_score = min(financial_score, 100)

    # 4. System health (low alerts = high score)
    # 100 - (alerts per school) * 5, floor at 0
    if active_schools:
        alert_ratio = (alerts_3m / active_schools) * 5
        health_score = max(round(100 - alert_ratio, 1), 0)
    else:
        health_score = 100

    # 5. User engagement (active users / total)
    engagement_score = round((users_3m / total_users * 100), 1) if total_users else 0
    engagement_score = min(engagement_score, 100)

    # Overall score
    overall_score = round(
        (activation_rate + student_score + financial_score + health_score + engagement_score) / 5, 1
    )

    # ---------- PREPARE CHART DATA ----------
    # Last 3 months labels (e.g., ["Jul 2026", "Aug 2026", "Sep 2026"])
    month_labels = []
    month_schools_data = []
    month_users_data = []
    month_payments_data = []

    for i in range(2, -1, -1):
        m = (now - timedelta(days=30 * i)).replace(day=1)
        label = m.strftime('%b %Y')
        month_labels.append(label)

        # Count schools that month
        month_start = m
        if i > 0:
            month_end = (now - timedelta(days=30 * (i - 1))).replace(day=1)
        else:
            month_end = now

        month_schools_data.append(
            School.objects.filter(created_at__gte=month_start, created_at__lt=month_end).count()
        )
        month_users_data.append(
            User.objects.filter(date_joined__gte=month_start, date_joined__lt=month_end).count()
        )
        payments_total = Payment.objects.filter(
            paid_at__gte=month_start, paid_at__lt=month_end
        ).aggregate(total=Sum('amount_kes'))['total'] or 0
        month_payments_data.append(float(payments_total))

    return render(request, 'dashboard/super_admin_performance.html', {
        'total_schools': total_schools,
        'active_schools': active_schools,
        'total_users': total_users,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_parents': total_parents,
        'total_staff': total_staff,
        'schools_3m': schools_3m,
        'users_3m': users_3m,
        'payments_3m': payments_3m,
        'invoices_3m': invoices_3m,
        'alerts_3m': alerts_3m,
        'critical_alerts': critical_alerts,

        # Scores
        'activation_rate': activation_rate,
        'student_score': student_score,
        'financial_score': financial_score,
        'health_score': health_score,
        'engagement_score': engagement_score,
        'overall_score': overall_score,

        # Chart data (JSON-safe)
        'month_labels': month_labels,
        'month_schools_data': month_schools_data,
        'month_users_data': month_users_data,
        'month_payments_data': month_payments_data,
    })


@login_required
def admin_student_detail(request, student_id):
    """Placeholder — will show student detail for admin."""
    messages.info(request, 'Student detail view coming soon.')
    return redirect('admin_attendance_overview')


