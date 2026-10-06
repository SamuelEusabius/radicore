"""
Core dashboard views:
- Role-based routing (redirect_to_own_dashboard)
- Super admin dashboard
- School admin dashboard
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from apps.accounts.decorators import school_staff_only


# ==========================================================
# ROLE-BASED ROUTING
# ==========================================================

def redirect_to_own_dashboard(request):
    """Send the user to their OWN dashboard based on their role."""
    role = request.user.role

    redirect_map = {
        'super_admin':    'dash_super_admin',
        'school_admin':   'dash_school_admin',
        'teacher':        'dash_teacher',
        'parent':         'dash_parent',
        'accountant':     'dash_accountant',
        'student':        'dash_student',
        'driver':         'driver_dashboard',
        'librarian':      'librarian_dashboard',
        'lab_technician': 'lab_technician_dashboard',
        'nurse':          'nurse_dashboard',
        'chief_chef':     'chief_chef_dashboard',
    }

    target = redirect_map.get(role)
    if target:
        return redirect(target)

    return redirect('landing')

    target = redirect_map.get(role)
    if target:
        return redirect(target)

    return redirect('landing')


# ==========================================================
# SUPER ADMIN DASHBOARD
# ==========================================================

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


# ==========================================================
# SCHOOL ADMIN DASHBOARD
# ==========================================================

@login_required
@school_staff_only
def school_admin_dash(request):
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.parents.models import Parent
    from apps.staff.models import NonTeachingStaff
    from apps.academics.models import ClassLevel, Subject
    from apps.finance.models import Invoice

    school = request.user.school

    students_qs = Student.objects.filter(school=school, is_active=True)
    teachers_qs = Teacher.objects.filter(school=school, is_active=True).select_related('user', 'current_class')
    parents_qs = Parent.objects.filter(user__school=school).select_related('user').prefetch_related('students')
    staff_qs = NonTeachingStaff.objects.filter(school=school, is_active=True).order_by('role', 'full_name')

    invoices = Invoice.objects.filter(student__school=school)
    total_outstanding = sum(i.balance for i in invoices)

    return render(request, 'dashboard/school_admin.html', {
        'student_count': students_qs.count(),
        'teacher_count': teachers_qs.count(),
        'parent_count': parents_qs.count(),
        'staff_count': staff_qs.count(),
        'class_count': ClassLevel.objects.filter(school=school).count(),
        'subject_count': Subject.objects.filter(school=school).count(),
        'total_outstanding': total_outstanding,
        'recent_students': students_qs.order_by('-created_at')[:5],
        'recent_teachers': teachers_qs[:5],
        'recent_parents': parents_qs[:5],
        'recent_staff': staff_qs[:5],
    })
    

def redirect_dashboard(request):
    """Send user to their own dashboard based on role."""
    role = request.user.role
    return redirect({
        'super_admin':         'dash_super_admin',
        'school_admin':        'dash_school_admin',
        'teacher':             'dash_teacher',
        'parent':              'dash_parent',
        'accountant':          'dash_accountant',
        'student':             'dash_student',
        'driver':              'driver_dashboard',
        'librarian':           'librarian_dashboard',
        'lab_technician':      'lab_technician_dashboard',
        'nurse':               'nurse_dashboard',
        'chief_chef':          'chief_chef_dashboard',
        'director_of_studies': 'dos_dashboard',
        'store_keeper':        'store_keeper_dashboard',
        'boarding_master':     'boarding_dashboard',
    }.get(role, 'landing'))
    
    # ============================================================
# PLACEHOLDER DASHBOARDS (until full modules are built)
# ============================================================

@login_required
def store_keeper_dashboard_placeholder(request):
    """Temporary — shows a 'coming soon' page for Store Keepers."""
    if request.user.role not in ('store_keeper', 'school_admin'):
        return redirect('dashboard_home')
    messages.info(
        request,
        'Store Keeper module is being built. Check back soon!'
    )
    return redirect('dashboard_home')


@login_required
def boarding_dashboard_placeholder(request):
    """Temporary — shows a 'coming soon' page for Boarding Masters."""
    if request.user.role not in ('boarding_master', 'school_admin'):
        return redirect('dashboard_home')
    messages.info(
        request,
        'Boarding module is being built. Check back soon!'
    )
    return redirect('dashboard_home')