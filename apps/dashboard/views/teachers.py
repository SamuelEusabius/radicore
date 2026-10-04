"""
Teacher views:
- Teacher list, add, delete
- Teacher dashboard and timetable
- Class teacher dashboard and workflows
- Class teacher parent/student views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count, Sum, Avg
from .timetable import TIMETABLE_PERIODS

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
    class_teacher_only,
)


@login_required
def teachers_list(request):
    """List all teachers with filters and stats."""
    if request.user.role != 'school_admin':
        return redirect('dashboard_home')

    from apps.teachers.models import Teacher
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    school = request.user.school
    base_qs = Teacher.objects.filter(school=school).select_related('user', 'current_class')

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    emp_filter = request.GET.get('employment', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = base_qs.order_by('user__first_name', 'user__last_name')

    if search:
        qs = qs.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(employee_number__icontains=search) |
            Q(tsc_number__icontains=search) |
            Q(subject_specialty__icontains=search)
        )

    if emp_filter:
        qs = qs.filter(employment_type=emp_filter)

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)
    elif status_filter == 'class_teacher':
        qs = qs.filter(is_class_teacher=True)

    # ---------- Stats ----------
    stats = {
        'total': base_qs.count(),
        'class_teachers': base_qs.filter(is_class_teacher=True).count(),
        'tsc': base_qs.filter(employment_type='tsc').count(),
        'bom': base_qs.filter(employment_type='bom').count(),
        'interns': base_qs.filter(employment_type='intern').count(),
        'contract': base_qs.filter(employment_type='contract').count(),
        'active': base_qs.filter(is_active=True).count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'dashboard/teachers_list.html', {
        'teachers': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'stats': stats,
        'search': search,
        'emp_filter': emp_filter,
        'status_filter': status_filter,
        'employment_types': Teacher.EmploymentType.choices,
        'total_filtered': qs.count(),
    })


@login_required
@teacher_only
def teacher_dash(request):
    """Teacher dashboard — classes, timetable, quick stats."""
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from apps.teachers.models import Teacher
    from apps.academics.models import ClassLevel, Timetable
    from datetime import date
    from django.db.models import Count, Q

    user = request.user
    school = user.school
    today = date.today()
    today_name = today.strftime('%a').upper()[:3]  # 'MON', 'TUE', etc.

    # ---------- Teacher profile ----------
    teacher = None
    try:
        teacher = Teacher.objects.select_related('current_class', 'user').get(user=user)
    except Teacher.DoesNotExist:
        pass

    # ---------- Students in my classes ----------
    # Get classes from timetable where I teach
    my_timetable = Timetable.objects.filter(
        school=school, teacher=user
    ).select_related('class_level', 'subject')

    my_class_names = list(
        my_timetable.values_list('class_level__name', flat=True).distinct()
    )

    # If class teacher, include their class
    if teacher and teacher.current_class:
        if teacher.current_class.name not in my_class_names:
            my_class_names.append(teacher.current_class.name)

    # Total students in my classes
    if my_class_names:
        student_count = Student.objects.filter(
            school=school, is_active=True, class_level__in=my_class_names
        ).count()
    else:
        student_count = 0

    # ---------- Attendance today ----------
    marked_today = Attendance.objects.filter(
        student__school=school,
        date=today,
        recorded_by=user,
    ).values('student').distinct().count()

    completion = round((marked_today / student_count) * 100) if student_count else 0

    # ---------- Today's timetable ----------
    today_classes = Timetable.objects.filter(
        school=school,
        teacher=user,
        day_of_week=today_name,
    ).select_related('class_level', 'subject').order_by('start_time')

    # ---------- My classes with student counts ----------
    my_classes = []
    for class_name in my_class_names:
        count = Student.objects.filter(
            school=school, is_active=True, class_level=class_name
        ).count()
        # Is this my class-teacher class?
        is_mine = teacher and teacher.current_class and teacher.current_class.name == class_name
        my_classes.append({
            'name': class_name,
            'count': count,
            'is_class_teacher': is_mine,
        })
    my_classes.sort(key=lambda x: x['name'])

    # ---------- Class teacher info ----------
    is_class_teacher = bool(teacher and teacher.is_class_teacher and teacher.current_class)

    # ---------- Class average (if class teacher) ----------
    class_average = None
    if is_class_teacher:
        from apps.grades.models import Grade
        cls_students = Student.objects.filter(
            school=school, class_level=teacher.current_class.name, is_active=True
        )
        agg = Grade.objects.filter(
            student__in=cls_students
        ).aggregate(
            total=Count('id'),
        )
        # If you want actual average, compute it in a helper

    return render(request, 'dashboard/teacher.html', {
        'student_count': student_count,
        'marked_today': marked_today,
        'completion': completion,
        'today': today,
        'teacher': teacher,
        'today_classes': today_classes,
        'my_classes': my_classes,
        'class_count': len(my_class_names),
        'is_class_teacher': is_class_teacher,
        'current_class': teacher.current_class if teacher else None,
    })


@login_required
def teacher_timetable(request):
    """View timetable for the currently logged-in teacher."""
    from apps.academics.models import Timetable

    user = request.user
    if user.role not in ('teacher', 'school_admin'):
        return redirect('dashboard_home')

    entries = Timetable.objects.filter(
        school=user.school, teacher=user
    ).select_related('subject', 'class_level')

    period_index = {p[0]: i for i, p in enumerate(TIMETABLE_PERIODS)}

    grid = {}
    for entry in entries:
        start_str = entry.start_time.strftime('%H:%M')
        if start_str in period_index:
            idx = period_index[start_str]
            grid.setdefault(idx, {})[entry.day_of_week] = entry

    return render(request, 'dashboard/teacher_timetable.html', {
        'grid': grid,
        'periods': TIMETABLE_PERIODS,
        'days': [
            ('MON', 'Monday'),
            ('TUE', 'Tuesday'),
            ('WED', 'Wednesday'),
            ('THU', 'Thursday'),
            ('FRI', 'Friday'),
            ('SAT', 'Saturday'),
        ],
    })


@login_required
def add_teacher(request):
    if request.user.role != 'school_admin':
        return redirect('dashboard_home')

    from apps.accounts.models import User
    from apps.teachers.models import Teacher
    from apps.academics.models import ClassLevel

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', '').strip()
        phone = request.POST.get('phone', '').strip()
        employee_number = request.POST.get('employee_number', '').strip()
        tsc_number = request.POST.get('tsc_number', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        subject_specialty = request.POST.get('subject_specialty', '').strip()
        employment_type = request.POST.get('employment_type', 'tsc')
        is_class_teacher = request.POST.get('is_class_teacher') == 'on'
        current_class_id = request.POST.get('current_class') or None
        hire_date = request.POST.get('hire_date') or None
        photo = request.FILES.get('photo')

        errors = []
        if not email:
            errors.append('Email is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if not first_name or not last_name:
            errors.append('First and last name are required.')
        if not employee_number:
            errors.append('Employee number is required.')

        if User.objects.filter(email=email).exists():
            errors.append(f'Email "{email}" is already registered.')

        if Teacher.objects.filter(school=school, employee_number=employee_number).exists():
            errors.append(f'Employee number "{employee_number}" is already used.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/add_teacher.html', {
                'classes': classes,
                'employment_types': Teacher.EmploymentType.choices,
                'form_data': request.POST,
            })

        # Create User
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='teacher',
            phone=phone,
            school=school,
        )

        # Create Teacher
        teacher = Teacher.objects.create(
            school=school,
            user=user,
            employee_number=employee_number,
            tsc_number=tsc_number,
            id_number=id_number,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            gender=gender,
            phone=phone,
            photo=photo,
            subject_specialty=subject_specialty,
            employment_type=employment_type,
            is_class_teacher=is_class_teacher,
            current_class_id=current_class_id,
            hire_date=hire_date,
        )

        messages.success(request, f'✅ Teacher "{teacher.user.get_full_name()}" added successfully.')
        return redirect('teachers_list')

    return render(request, 'dashboard/add_teacher.html', {
        'classes': classes,
        'employment_types': Teacher.EmploymentType.choices,
    })


@login_required
def delete_teacher(request, teacher_id):
    if request.user.role != 'school_admin':
        return redirect('dashboard_home')

    from apps.teachers.models import Teacher
    teacher = get_object_or_404(Teacher, id=teacher_id, school=request.user.school)

    if request.method == 'POST':
        name = teacher.user.get_full_name() or teacher.user.email
        # Delete user (cascades to teacher)
        teacher.user.delete()
        messages.success(request, f'🗑️ Teacher "{name}" deleted.')
        return redirect('teachers_list')

    return render(request, 'dashboard/delete_teacher.html', {'teacher': teacher})


@login_required
@class_teacher_only
def class_teacher_dashboard(request):
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from apps.grades.models import Grade
    from apps.finance.models import Invoice
    from apps.parents.models import Parent
    from django.db.models import Sum, Count, Avg, F
    from datetime import date, timedelta

    user = request.user

    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        messages.error(request, 'No teacher profile linked to your account.')
        return redirect('dashboard_home')

    if not teacher.current_class:
        messages.warning(
            request,
            'You are not currently assigned as a class teacher. Contact the school admin.'
        )
        return render(request, 'dashboard/class_teacher.html', {
            'teacher': teacher, 'no_class': True,
        })

    cls = teacher.current_class
    today = date.today()

    # Roster — annotate with photo, fees, attendance
    students = (
        Student.objects
        .filter(school=user.school, class_level=cls.name, is_active=True)
        .order_by('first_name', 'last_name')
    )
    student_ids = list(students.values_list('id', flat=True))

    # Attendance today
    today_attendance = Attendance.objects.filter(
        student_id__in=student_ids, date=today
    ).select_related('student')
    attendance_map = {a.student_id: a for a in today_attendance}

    present_today = sum(1 for a in today_attendance if a.status == 'P')
    absent_today  = sum(1 for a in today_attendance if a.status == 'A')
    late_today    = sum(1 for a in today_attendance if a.status == 'L')
    marked_today  = today_attendance.count()
    not_marked    = len(student_ids) - marked_today

    # Class average (all grades, no N+1)
    grade_agg = Grade.objects.filter(
        student_id__in=student_ids
    ).aggregate(
        total_marks=Sum('marks'),
        total_out_of=Sum('out_of'),
    )
    total_marks  = grade_agg['total_marks']  or 0
    total_out_of = grade_agg['total_out_of'] or 1
    class_average = round((float(total_marks) / float(total_out_of)) * 100, 1)

    # Fees snapshot
    invoice_agg = Invoice.objects.filter(
        student_id__in=student_ids
    ).aggregate(
        total_due=Sum('amount_due'),
        total_paid=Sum('amount_paid'),
    )
    total_due  = invoice_agg['total_due']  or 0
    total_paid = invoice_agg['total_paid'] or 0
    outstanding = total_due - total_paid

    # Students with balance
    student_balances = (
        Invoice.objects
        .filter(student_id__in=student_ids, status__in=['unpaid', 'partial', 'overdue'])
        .values('student_id')
        .annotate(bal=Sum(F('amount_due') - F('amount_paid')))
    )
    balance_map = {row['student_id']: float(row['bal'] or 0) for row in student_balances}

    # Parent count for this class
    parent_count = Parent.objects.filter(students__in=student_ids).distinct().count()

    # Recent grades
    recent_grades = (
        Grade.objects
        .filter(student_id__in=student_ids)
        .select_related('student', 'subject', 'exam')
        .order_by('-exam__year', '-exam__id')[:15]
    )

    return render(request, 'dashboard/class_teacher.html', {
        'teacher': teacher,
        'cls': cls,
        'today': today,
        'students': students,
        'attendance_map': attendance_map,
        'present_today': present_today,
        'absent_today': absent_today,
        'late_today': late_today,
        'marked_today': marked_today,
        'not_marked': not_marked,
        'total_students': len(student_ids),
        'class_average': class_average,
        'total_due': total_due,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'balance_map': balance_map,
        'parent_count': parent_count,
        'recent_grades': recent_grades,
        'no_class': False,
    })


@login_required
@class_teacher_only
def class_teacher_parents(request):
    """List all parents whose children are in the class teacher's class."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.parents.models import Parent
    from django.db.models import Q

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        messages.error(request, 'No teacher profile linked to your account.')
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    # Students in my class
    class_students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    )
    class_student_ids = list(class_students.values_list('id', flat=True))

    # Parents whose children are in my class
    parents_qs = (
        Parent.objects
        .filter(students__in=class_student_ids)
        .select_related('user')
        .prefetch_related('students')
        .distinct()
    )

    # Optional search
    search = request.GET.get('q', '').strip()
    if search:
        parents_qs = parents_qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(user__email__icontains=search)
        )

    # Annotate each parent with which of their children are in this class
    parents = list(parents_qs)
    for p in parents:
        p.class_children = [
            s for s in p.students.all()
            if s.id in class_student_ids
        ]

    return render(request, 'dashboard/class_teacher_parents.html', {
        'teacher': teacher,
        'cls': cls,
        'parents': parents,
        'total_parents': len(parents),
        'search': search,
    })


@login_required
@class_teacher_only
def class_teacher_view_parent(request, parent_id):
    """View a single parent's bio and children."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.parents.models import Parent

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    # Only allow viewing parents of students in this class
    class_students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    )
    class_student_ids = list(class_students.values_list('id', flat=True))

    parent = get_object_or_404(
        Parent.objects
        .filter(students__in=class_student_ids)
        .select_related('user')
        .distinct(),
        id=parent_id
    )

    children = parent.students.all()

    return render(request, 'dashboard/class_teacher_view_parent.html', {
        'teacher': teacher,
        'cls': cls,
        'parent': parent,
        'children': children,
    })


@login_required
@class_teacher_only
def class_teacher_view_student(request, student_id):
    """View a single student (class-teacher scoped)."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.parents.models import Parent
    from apps.attendance.models import Attendance
    from apps.grades.models import Grade
    from apps.finance.models import Invoice

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    # Only allow viewing students in this class
    student = get_object_or_404(
        Student,
        id=student_id,
        school=user.school,
        class_level=cls.name,
    )

    parents = student.parents.all()

    # Attendance summary (last 30 days)
    from datetime import date, timedelta
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_attendance = Attendance.objects.filter(
        student=student, date__gte=thirty_days_ago
    ).order_by('-date')[:30]

    present = sum(1 for a in recent_attendance if a.status == 'P')
    absent = sum(1 for a in recent_attendance if a.status == 'A')
    late = sum(1 for a in recent_attendance if a.status == 'L')

    # Recent grades
    recent_grades = Grade.objects.filter(
        student=student
    ).select_related('subject', 'exam').order_by('-exam__year', '-exam__id')[:10]

    # Fees
    invoice_agg = Invoice.objects.filter(student=student).aggregate(
        total_due=Sum('amount_due'), total_paid=Sum('amount_paid')
    )
    total_due = invoice_agg['total_due'] or 0
    total_paid = invoice_agg['total_paid'] or 0
    outstanding = total_due - total_paid

        # Co-curricular activities
    activities = student.activities.all()[:10] if hasattr(student, 'activities') else []

    return render(request, 'dashboard/class_teacher_view_student.html', {
        'teacher': teacher,
        'cls': cls,
        'student': student,
        'parents': parents,
        'present': present,
        'absent': absent,
        'late': late,
        'attendance_days': len(recent_attendance),
        'recent_grades': recent_grades,
        'activities': activities,
        'today': date.today(),
        'total_due': total_due,
        'total_paid': total_paid,
        'outstanding': outstanding,
    })


@login_required
@class_teacher_only
def class_teacher_parents_download(request):
    """Download parent contact list as CSV."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.parents.models import Parent
    from django.http import HttpResponse
    import csv

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    class_students = Student.objects.filter(
        school=user.school, class_level=cls.name, is_active=True,
    )
    class_student_ids = list(class_students.values_list('id', flat=True))

    parents = (
        Parent.objects
        .filter(students__in=class_student_ids)
        .select_related('user')
        .prefetch_related('students')
        .distinct()
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="parents_{cls.name.replace(" ", "_")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'First Name', 'Last Name', 'Relationship', 'Phone',
        'Email', 'ID Number', 'Occupation', 'Children in Class'
    ])

    for p in parents:
        class_children = [s for s in p.students.all() if s.id in class_student_ids]
        child_names = ', '.join(
            f"{c.full_name} ({c.admission_number})" for c in class_children
        )
        writer.writerow([
            p.first_name, p.last_name, p.get_relationship_display(),
            p.phone, p.user.email, p.id_number, p.occupation,
            child_names,
        ])

    return response


def _ct_teacher_and_class(request):
    """Helper — returns (teacher, cls) or (None, None) if invalid."""
    from apps.teachers.models import Teacher
    try:
        teacher = Teacher.objects.select_related('current_class', 'user').get(user=request.user)
    except Teacher.DoesNotExist:
        return None, None
    if not teacher.current_class:
        return teacher, None
    return teacher, teacher.current_class


