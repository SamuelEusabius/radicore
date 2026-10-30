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
from apps.core.pdf_utils import build_pdf_context


@login_required
def students_list(request):
    """List all students with filters, search, and pagination."""
    if request.user.role not in ('principal', 'super_admin', 'secretary', 'deputy_admin', 'deputy_academics', 'director_of_studies', 'class_teacher', 'teacher'):
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


def generate_next_admission_number(school):
    """Generate the next admission number starting from 1."""
    from apps.students.models import Student
    from django.db.models import Max
    import re

    # Get all admission numbers for this school
    numbers = Student.objects.filter(school=school).exclude(admission_number__isnull=True).exclude(admission_number='').values_list('admission_number', flat=True)
    
    highest_num = 0
    for num in numbers:
        # Extract just the digits if there is a prefix (e.g., ADM-5 -> 5)
        match = re.search(r'(\d+)$', str(num))
        if match:
            val = int(match.group(1))
            if val > highest_num:
                highest_num = val
                
    return str(highest_num + 1)

@login_required
def add_student(request):
    """Directly add a student to the system."""
    if request.user.role not in ('principal', 'secretary', 'super_admin', 'deputy_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.locations.models import County, Constituency, Ward

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    counties = County.objects.all().order_by('name')

    if request.method == 'POST':
        # --- 1. Personal Details ---
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', 'M')
        date_of_birth = request.POST.get('date_of_birth') or None
        class_level = request.POST.get('class_level')
        admission_date = request.POST.get('admission_date') or None
        
        # --- 2. Guardian Details ---
        guardian_name = request.POST.get('guardian_name', '').strip()
        guardian_phone = request.POST.get('guardian_phone', '').strip()
        parent_id_number = request.POST.get('parent_id_number', '').strip()
        
        # --- 3. Location (IDs from dropdowns) ---
        county_id = request.POST.get('county_fk') or None
        constituency_id = request.POST.get('constituency_fk') or None
        ward_id = request.POST.get('ward_fk') or None
        village = request.POST.get('village', '').strip()
        
        # --- 4. Documents & Previous School ---
        birth_certificate_number = request.POST.get('birth_certificate_number', '').strip()
        upi = request.POST.get('upi', '').strip()
        previous_school_marks = request.POST.get('previous_school_marks', '').strip()
        previous_school_mean_grade = request.POST.get('previous_school_mean_grade', '').strip()
        
        # --- 5. Boarding ---
        is_boarding = request.POST.get('is_boarding') == 'on'

        # --- 6. Validation ---
        errors = []
        if not first_name or not last_name:
            errors.append("First and Last name are required.")
        if not class_level:
            errors.append("Class Level is required.")
            
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'dashboard/add_student.html', {
                'classes': classes,
                'counties': counties,
                'form_data': request.POST,
                'next_admission_number': generate_next_admission_number(school),
            })

        # --- 7. Generate Admission Number ---
        admission_number = generate_next_admission_number(school)

        # --- 8. Create the Student ---
        try:
            student = Student.objects.create(
                school=school,
                admission_number=admission_number,
                first_name=first_name,
                middle_name=middle_name,
                last_name=last_name,
                gender=gender,
                date_of_birth=date_of_birth,
                class_level=class_level,
                admission_date=admission_date,
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                parent_id_number=parent_id_number,
                county_fk_id=county_id,
                constituency_fk_id=constituency_id,
                ward_fk_id=ward_id,
                village=village,
                birth_certificate_number=birth_certificate_number,
                upi=upi,
                previous_school_marks=previous_school_marks,
                previous_school_mean_grade=previous_school_mean_grade,
                is_boarding=is_boarding,
                photo=request.FILES.get('photo'),
                is_active=True
            )
            messages.success(request, f"Student {student.full_name} added successfully! Adm No: {admission_number}")
            return redirect('students_list')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'dashboard/add_student.html', {
                'classes': classes,
                'counties': counties,
                'form_data': request.POST,
                'next_admission_number': generate_next_admission_number(school),
            })

    # --- GET Request ---
    return render(request, 'dashboard/add_student.html', {
        'classes': classes,
        'counties': counties,
        'next_admission_number': generate_next_admission_number(school),
    })

def generate_next_admission_number(school):
    """Generate the next admission number starting from the school's configured baseline."""
    from apps.students.models import Student
    import re

    numbers = (
        Student.objects.filter(school=school)
        .exclude(admission_number__isnull=True)
        .exclude(admission_number='')
        .values_list('admission_number', flat=True)
    )
    
    highest_num = 0
    for num in numbers:
        match = re.search(r'(\d+)$', str(num))
        if match:
            val = int(match.group(1))
            if val > highest_num:
                highest_num = val
                
    # The baseline is the number the Principal set in Settings
    baseline = school.starting_admission_number or 1

    # If the highest number found is less than the baseline, 
    # it means we are starting a new series.
    if highest_num < baseline:
        return str(baseline)
        
    return str(highest_num + 1)


@login_required
def delete_student(request, student_id):
    if request.user.role != 'principal':
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
    if request.user.role != 'principal':
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
    if request.user.role != 'principal':
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
    if request.user.role != 'principal':
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

    # ---------- Base64 images for xhtml2pdf ----------
    from apps.core.pdf_utils import get_school_logo_data_uri

    # School logo → base64
    school_logo_b64 = get_school_logo_data_uri(student.school, max_width=120)

    # Coat of arms → base64
    import os as _os
    from django.conf import settings as dj_settings
    import base64 as b64

    coat_of_arms_b64 = None
    coat_path = _os.path.join(str(dj_settings.BASE_DIR), 'static', 'images', 'coat_of_arms.png')
    if _os.path.exists(coat_path):
        try:
            with open(coat_path, 'rb') as f:
                coat_of_arms_b64 = 'data:image/png;base64,' + b64.b64encode(f.read()).decode('ascii')
        except Exception:
            coat_of_arms_b64 = None

    html_string = render_to_string('pdf/leaving_certificate.html',
        build_pdf_context(
            school=student.school,
            generated_by=request.user,
            student=student,
            content=content,
            printed_by=request.user,
            school_logo_b64=school_logo_b64,
            coat_of_arms_b64=coat_of_arms_b64,
        )
    )


    filename = f'leaving_certificate_{student.admission_number}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
def student_biodata_pdf(request, student_id):
    """Generate a professional Student Bio Data PDF."""
    if request.user.role not in ('principal', 'accountant'):
        return redirect('dashboard_home')

    import os
    import base64 as b64
    from django.conf import settings as dj_settings
    from django.template.loader import render_to_string

    from apps.students.models import Student
    from apps.core.pdf_utils import (
        html_to_pdf_response, build_pdf_context, image_to_base64,
        get_school_logo_data_uri,
    )

    student = get_object_or_404(Student, id=student_id, school=request.user.school)

    # School logo
    school_logo_b64 = get_school_logo_data_uri(student.school, max_width=120)

    # Student photo
    student_photo_b64 = None
    if student.photo:
        student_photo_b64 = image_to_base64(student.photo, max_width=240)

    # Kenya coat of arms (from static images)
    coat_of_arms_b64 = None
    coat_path = os.path.join(str(dj_settings.BASE_DIR), 'static', 'images', 'coat_of_arms.png')
    if os.path.exists(coat_path):
        try:
            with open(coat_path, 'rb') as f:
                coat_of_arms_b64 = 'data:image/png;base64,' + b64.b64encode(f.read()).decode('ascii')
        except Exception:
            coat_of_arms_b64 = None

    html_string = render_to_string('pdf/student_biodata.html',
        build_pdf_context(
            school=student.school,
            generated_by=request.user,
            student=student,
            printed_by=request.user,
            school_logo_b64=school_logo_b64,
            student_photo_b64=student_photo_b64,
            coat_of_arms_b64=coat_of_arms_b64,
        )
    )

    filename = f'biodata_{student.admission_number or student.id}.pdf'
    return html_to_pdf_response(html_string, filename)

@login_required
def student_detail(request, student_id):
    """Full student profile — admin/teacher/accountant view."""
    if request.user.role not in ('principal', 'accountant', 'teacher'):
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
    if not school:
      return redirect('dashboard_home')
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

@login_required
def student_bio_page(request, student_id):
    """Full bio-data page (HTML, printable) for a single student."""
    from apps.students.models import Student
    from django.shortcuts import get_object_or_404

    student = get_object_or_404(
        Student.objects.select_related(
            'school', 'county_fk', 'constituency_fk', 'ward_fk', 'user',
        ),
        id=student_id, school=request.user.school,
    )

    # Parents
    parents = student.parents.select_related('user') if hasattr(student, 'parents') else []

    # Boarding
    boarding = student.boarding_assignments.filter(status='active').select_related(
        'dormitory', 'bed'
    ).first()

    return render(request, 'dashboard/student_bio.html', {
        'student': student,
        'parents': parents,
        'boarding': boarding,
        'school': request.user.school,
    })
    
@login_required
def edit_student(request, student_id):
    """Edit an existing student's details."""
    if request.user.role not in ('principal', 'secretary', 'super_admin', 'deputy_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.locations.models import County

    school = request.user.school
    student = get_object_or_404(Student, id=student_id, school=school)
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    counties = County.objects.all().order_by('name')

    if request.method == 'POST':
        # Update basic details
        student.first_name = request.POST.get('first_name', '').strip()
        student.middle_name = request.POST.get('middle_name', '').strip()
        student.last_name = request.POST.get('last_name', '').strip()
        student.gender = request.POST.get('gender', 'M')
        student.date_of_birth = request.POST.get('date_of_birth') or None
        student.class_level = request.POST.get('class_level')
        student.guardian_name = request.POST.get('guardian_name', '').strip()
        student.guardian_phone = request.POST.get('guardian_phone', '').strip()
        student.parent_id_number = request.POST.get('parent_id_number', '').strip()
        student.birth_certificate_number = request.POST.get('birth_certificate_number', '').strip()
        student.upi = request.POST.get('upi', '').strip()
        student.is_boarding = request.POST.get('is_boarding') == 'on'
        
        # Handle location safely (only if they are valid IDs)
        if request.POST.get('county_fk'): student.county_fk_id = request.POST.get('county_fk')
        if request.POST.get('constituency_fk'): student.constituency_fk_id = request.POST.get('constituency_fk')
        if request.POST.get('ward_fk'): student.ward_fk_id = request.POST.get('ward_fk')

        # Handle photo upload
        if 'photo' in request.FILES:
            student.photo = request.FILES['photo']

        student.save()
        messages.success(request, f"Student {student.full_name} updated successfully.")
        return redirect('students_list')

    # For GET, we need to pass the student data back to the form
    # The template expects 'form_data', so we mock it
    form_data = {
        'first_name': student.first_name,
        'middle_name': student.middle_name,
        'last_name': student.last_name,
        'gender': student.gender,
        'date_of_birth': student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else '',
        'class_level': student.class_level,
        'guardian_name': student.guardian_name,
        'guardian_phone': student.guardian_phone,
        'parent_id_number': student.parent_id_number,
        'birth_certificate_number': student.birth_certificate_number,
        'upi': student.upi,
        'is_boarding': student.is_boarding,
    }

    return render(request, 'dashboard/add_student.html', {
        'classes': classes,
        'counties': counties,
        'form_data': form_data,
        'is_edit': True, # We can use this to change the title/button
        'student': student,
    })


@login_required
def link_parent_to_student(request, student_id):
    """Manually link an existing parent or create a new one for a student."""
    if request.user.role not in ('principal', 'secretary', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.parents.models import Parent
    from apps.accounts.models import User

    school = request.user.school
    student = get_object_or_404(Student, id=student_id, school=school)
    
    # Get all parents in this school
    existing_parents = Parent.objects.filter(user__school=school).select_related('user')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'link_existing':
            parent_id = request.POST.get('parent_id')
            parent = get_object_or_404(Parent, id=parent_id, user__school=school)
            parent.students.add(student)
            messages.success(request, f"Linked parent {parent.first_name} {parent.last_name} to {student.full_name}.")
            return redirect('students_list')

        elif action == 'create_new':
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            phone = request.POST.get('phone')
            email = request.POST.get('email')
            id_number = request.POST.get('id_number')
            password = '12345678'

            if not User.objects.filter(email=email).exists():
                user = User.objects.create_user(
                    username=email, email=email, password=password,
                    first_name=first_name, last_name=last_name,
                    role='parent', school=school
                )
                parent = Parent.objects.create(
                    user=user, first_name=first_name, last_name=last_name, 
                    phone=phone, id_number=id_number
                )
                parent.students.add(student)
                messages.success(request, f"Created parent account {email} and linked. Password: {password}")
            else:
                messages.error(request, f"A user with email {email} already exists.")
            
            return redirect('students_list')

    # Create a list of parents to pass to the Javascript for searching
    parent_data = []
    for p in existing_parents:
        label = f"{p.first_name} {p.last_name} | Phone: {p.phone or '—'} | ID: {p.id_number or '—'}"
        parent_data.append({'id': p.id, 'label': label})

    return render(request, 'dashboard/link_parent.html', {
        'student': student,
        'parents': existing_parents,
        'parent_data': parent_data,
    })