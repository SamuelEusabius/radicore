"""
Student views:
- Student list, add, delete, detail
- Student dashboard
- Student lifecycle: clearance, leaving certificate, biodata
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count, Sum, Avg

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
    parent_only, student_only, accountant_only,
)


@login_required
def students_list(request):
    """List all students with filters, search, and pagination."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from django.db import models as db_models
    from django.core.paginator import Paginator
    from django.db.models import Q

    school = request.user.school
    qs = Student.objects.filter(school=school).order_by('class_level', 'first_name', 'last_name')

    # ---------- Filters ----------
    search = request.GET.get('q', '').strip()
    level = request.GET.get('level', '').strip()
    class_filter = request.GET.get('class', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(middle_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(admission_number__icontains=search) |
            Q(upi__icontains=search)
        )
    if level:
        qs = qs.filter(cbc_level=level)
    if class_filter:
        qs = qs.filter(class_level=class_filter)
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)
    elif status_filter == 'cleared':
        qs = qs.filter(is_cleared=True)

    # ---------- Stats (unfiltered by search, scoped to school) ----------
    all_school_students = Student.objects.filter(school=school)
    stats = {
        'total': all_school_students.count(),
        'boys': all_school_students.filter(gender='M').count(),
        'girls': all_school_students.filter(gender='F').count(),
        'active': all_school_students.filter(is_active=True).count(),
    }

    # ---------- Pagination ----------
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # ---------- Class levels for filter ----------
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    return render(request, 'dashboard/students_list.html', {
        'students': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'search': search,
        'level': level,
        'class_filter': class_filter,
        'status_filter': status_filter,
        'cbc_levels': Student.CBCLevel.choices,
        'classes': classes,
        'total': qs.count(),
        'stats': stats,
    })


@login_required
@student_only
def student_dash(request):
    from apps.students.models import Student
    from apps.grades.models import Grade
    from apps.attendance.models import Attendance
    from apps.finance.models import Invoice

    # Get the student profile
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        # Profile not linked → show friendly page (NO redirect)
        return render(request, 'dashboard/student_unlinked.html', {})

    # Grades
    grades = Grade.objects.filter(student=student).select_related('subject', 'exam').order_by('-exam__year', '-exam__id')

    # Attendance summary
    attendance_qs = Attendance.objects.filter(student=student).order_by('-date')
    total_days = attendance_qs.count()
    present_days = attendance_qs.filter(status='P').count()
    absent_days = attendance_qs.filter(status='A').count()
    late_days = attendance_qs.filter(status='L').count()
    attendance_rate = round((present_days / total_days) * 100, 1) if total_days else 0

    # Average grade
    if grades:
        avg_percentage = sum(g.percentage for g in grades) / len(grades)
    else:
        avg_percentage = 0

    # Invoices
    invoices = Invoice.objects.filter(student=student).select_related('fee_structure')
    total_due = sum(i.balance for i in invoices)

    return render(request, 'dashboard/student.html', {
        'student': student,
        'grades': grades,
        'attendance': attendance_qs[:30],
        'total_days': total_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'attendance_rate': attendance_rate,
        'avg_percentage': round(avg_percentage, 1),
        'invoices': invoices,
        'total_due': total_due,
    })


@login_required
def add_student(request):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', '').strip()
        date_of_birth = request.POST.get('date_of_birth') or None
        upi = request.POST.get('upi', '').strip()
        birth_certificate_number = request.POST.get('birth_certificate_number', '').strip()
        cbc_level = request.POST.get('cbc_level', '').strip()
        class_level = request.POST.get('class_level', '').strip()
        admission_date = request.POST.get('admission_date') or None
        guardian_name = request.POST.get('guardian_name', '').strip()
        guardian_phone = request.POST.get('guardian_phone', '').strip()
        guardian_relationship = request.POST.get('guardian_relationship', '').strip()
        has_special_needs = request.POST.get('has_special_needs') == 'on'
        special_needs_notes = request.POST.get('special_needs_notes', '').strip()
        photo = request.FILES.get('photo')

        # Auto-generate admission number if requested
        admission_number = request.POST.get('admission_number', '').strip()
        auto_generate = request.POST.get('auto_generate_admission') == 'on'
        start_from = request.POST.get('start_from', '1').strip()
        try:
            start_from = int(start_from)
        except ValueError:
            start_from = 1

        if auto_generate and not admission_number:
            if not gender:
                messages.error(request, 'Please select gender first to auto-generate admission number.')
                return render(request, 'dashboard/add_student.html', {
                    'cbc_levels': Student.CBCLevel.choices,
                    'form_data': request.POST,
                })
            admission_number = Student.generate_admission_number(
                school=request.user.school,
                gender=gender,
                start_from=start_from,
            )

        errors = []
        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        if not gender:
            errors.append('Gender is required.')
        if not admission_number:
            errors.append('Admission number is required.')
        elif Student.objects.filter(school=request.user.school, admission_number=admission_number).exists():
            errors.append(f'Admission number {admission_number} is already used.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/add_student.html', {
                'cbc_levels': Student.CBCLevel.choices,
                'form_data': request.POST,
            })

        student = Student.objects.create(
            school=request.user.school,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            gender=gender,
            date_of_birth=date_of_birth,
            admission_number=admission_number,
            upi=upi,
            birth_certificate_number=birth_certificate_number,
            cbc_level=cbc_level,
            class_level=class_level,
            admission_date=admission_date,
            guardian_name=guardian_name,
            guardian_phone=guardian_phone,
            guardian_relationship=guardian_relationship,
            has_special_needs=has_special_needs,
            special_needs_notes=special_needs_notes,
            photo=photo,
        )

        messages.success(request, f'Student "{student.full_name}" added (Adm: {student.admission_number}).')
        # Redirect to the bio data PDF for immediate download
        return redirect('student_biodata_pdf', student_id=student.id)

    return render(request, 'dashboard/add_student.html', {
        'cbc_levels': Student.CBCLevel.choices,
    })


@login_required
def delete_student(request, student_id):
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    if request.method == 'POST':
        name = student.full_name
        student.delete()
        messages.success(request, f'Student "{name}" deleted.')
        return redirect('students_list')

    return render(request, 'dashboard/delete_student.html', {'student': student})


@login_required
def clear_student(request, student_id):
    """Mark a student as cleared and open the leaving certificate editor."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from django.utils import timezone

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    if request.method == 'POST':
        student.is_cleared = True
        student.cleared_at = timezone.now()
        student.clearance_reason = request.POST.get('clearance_reason', '').strip()
        student.leaving_certificate_notes = request.POST.get('certificate_notes', '').strip()
        student.is_active = False  # soft-deactivate
        student.save()

        messages.success(request, f'✅ {student.full_name} has been cleared.')
        return redirect('leaving_certificate', student_id=student.id)

    return render(request, 'dashboard/clear_student.html', {'student': student})


@login_required
def leaving_certificate(request, student_id):
    """Editor for the leaving certificate."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    return render(request, 'dashboard/leaving_certificate.html', {
        'student': student,
        'school': request.user.school,
    })


@login_required
def leaving_certificate_pdf(request, student_id):
    """Generate the leaving certificate PDF with rich content and Coat of Arms."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from django.conf import settings
    import os

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    if request.method == 'POST':
        # Save the edited content before generating
        content = request.POST.get('content_html', '').strip()
        reason = request.POST.get('clearance_reason', '').strip()

        if content:
            student.leaving_certificate_content = content
        if reason:
            student.clearance_reason = reason

        # Optional extra fields
        student.leaving_certificate_notes = request.POST.get('certificate_notes', '').strip()

        student.save()

    # Fallback content if none provided
    content = student.leaving_certificate_content
    if not content:
        # Build default content
        content = f"""
        <p style="text-align: justify;">This is to certify that <strong>{student.full_name}</strong>
        {f"(Admission No: <strong>{student.admission_number}</strong>)" if student.admission_number else ""}
        was a bona fide student of <strong>{student.school.name}</strong>
        {f"in <strong>{student.class_level}</strong>" if student.class_level else ""}
        {f"from <strong>{student.admission_date.strftime('%d %B %Y')}</strong>" if student.admission_date else ""}
        {f"to <strong>{student.cleared_at.strftime('%d %B %Y')}</strong>" if student.cleared_at else ""}.</p>

        <p style="text-align: justify;">The student's conduct during this period was <strong>{student.clearance_reason or 'Good'}</strong>.</p>

        <p style="text-align: justify;">We wish the student every success in their future endeavours.</p>
        """

    # ---------- Resolve Coat of Arms absolute path ----------
    # xhtml2pdf needs an absolute file path — {% static %} won't work.
    coat_of_arms_path = os.path.join(
        str(settings.BASE_DIR), 'static', 'images', 'coat_of_arms.png'
    )
    if not os.path.exists(coat_of_arms_path):
        coat_of_arms_path = ''

    # ---------- Resolve School logo absolute path ----------
    school_logo_path = ''
    if student.school.logo:
        try:
            school_logo_path = student.school.logo.path
            if not os.path.exists(school_logo_path):
                school_logo_path = ''
        except (ValueError, NotImplementedError):
            school_logo_path = ''

    html_string = render_to_string('pdf/leaving_certificate.html', {
        'student': student,
        'school': student.school,
        'content': content,
        'printed_by': request.user,
        'coat_of_arms_path': coat_of_arms_path,
        'school_logo_path': school_logo_path,
    })

    filename = f'leaving_certificate_{student.admission_number}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
def student_biodata_pdf(request, student_id):
    """Generate a downloadable PDF of the student's bio data."""
    if request.user.role not in ('school_admin', 'super_admin', 'accountant'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    html_string = render_to_string('pdf/student_biodata.html', {
        'student': student,
        'school': student.school,
        'printed_by': request.user,
    })

    filename = f'biodata_{student.admission_number}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
def student_detail(request, student_id):
    """Full student profile — admin/teacher/accountant view."""
    if request.user.role not in ('school_admin', 'super_admin', 'accountant', 'teacher'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.finance.models import Invoice, Payment
    from apps.grades.models import Grade
    from apps.attendance.models import Attendance
    from apps.parents.models import Parent
    from django.db.models import Sum, Count, Q
    from datetime import date, timedelta

    school = request.user.school

    # Super admin can see any student (but no school = no scope, use student's school)
    if request.user.role == 'super_admin' and not school:
        student = get_object_or_404(Student, id=student_id)
    else:
        student = get_object_or_404(Student, id=student_id, school=school)

    # ---------- Parents ----------
    parents = Parent.objects.filter(students=student).select_related('user')

    # ---------- Siblings (share a parent) ----------
    sibling_ids = set()
    for p in parents:
        for sib in p.students.all():
            if sib.id != student.id:
                sibling_ids.add(sib.id)
    siblings = Student.objects.filter(id__in=sibling_ids)

    # ---------- Fees ----------
    invoices = Invoice.objects.filter(
        student=student
    ).select_related('fee_structure').order_by('-created_at')

    invoice_agg = invoices.aggregate(
        total_due=Sum('amount_due'),
        total_paid=Sum('amount_paid'),
    )
    total_invoiced = float(invoice_agg['total_due'] or 0)
    total_paid = float(invoice_agg['total_paid'] or 0)
    total_balance = total_invoiced - total_paid

    # ---------- Payments ----------
    payments = Payment.objects.filter(
        invoice__student=student
    ).select_related('invoice').order_by('-paid_at')[:20]

    # ---------- Grades ----------
    grades = Grade.objects.filter(
        student=student
    ).select_related('subject', 'exam').order_by('-exam__year', '-exam__id', 'subject__name')

    # Average percentage
    if grades:
        total_marks = sum(float(g.marks) for g in grades)
        total_out_of = sum(float(g.out_of) for g in grades) or 1
        avg_percentage = round((total_marks / total_out_of) * 100, 1)
    else:
        avg_percentage = 0

    # ---------- Attendance (last 30 days) ----------
    thirty_days_ago = date.today() - timedelta(days=30)
    recent_attendance = Attendance.objects.filter(
        student=student, date__gte=thirty_days_ago
    ).order_by('-date')

    present_30 = recent_attendance.filter(status='P').count()
    absent_30 = recent_attendance.filter(status='A').count()
    late_30 = recent_attendance.filter(status='L').count()
    excused_30 = recent_attendance.filter(status='E').count()
    total_marked_30 = present_30 + absent_30 + late_30 + excused_30
    attendance_rate = round((present_30 / total_marked_30) * 100, 1) if total_marked_30 else 0

    # All-time attendance rate
    all_att = Attendance.objects.filter(student=student)
    all_att_total = all_att.count()
    all_att_present = all_att.filter(status='P').count()
    lifetime_attendance = round((all_att_present / all_att_total) * 100, 1) if all_att_total else 0

    return render(request, 'dashboard/student_detail.html', {
        'student': student,
        'parents': parents,
        'siblings': siblings,
        'invoices': invoices,
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'payments': payments,
        'grades': grades,
        'avg_percentage': avg_percentage,
        'recent_attendance': recent_attendance[:30],
        'present_30': present_30,
        'absent_30': absent_30,
        'late_30': late_30,
        'excused_30': excused_30,
        'attendance_rate': attendance_rate,
        'lifetime_attendance': lifetime_attendance,
        'today': date.today(),
    })


