"""
Attendance views:
- Teacher attendance (marking)
- Class teacher attendance (marking, sheet, PDF)
- Admin attendance overview (school-wide)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count, Sum

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
    class_teacher_only,
)


@login_required
@role_required('teacher', 'school_admin', 'super_admin')
def teacher_attendance(request):
    """Mark attendance for a class — modern responsive layout."""
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from apps.academics.models import ClassLevel
    from datetime import date, datetime, timedelta

    school = request.user.school

    # ---------- Date ----------
    date_str = request.GET.get('date') or request.POST.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        selected_date = date.today()

    # Prevent future dates
    if selected_date > date.today():
        selected_date = date.today()

    # ---------- Class ----------
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    class_id = request.GET.get('class') or request.POST.get('class')

    if not class_id and classes.exists():
        class_id = classes.first().id

    selected_class = None
    students = []
    rows = []

    if class_id:
        try:
            if str(class_id).isdigit():
                selected_class = ClassLevel.objects.get(id=int(class_id), school=school)
            else:
                selected_class = ClassLevel.objects.get(name=class_id, school=school)
            class_id = selected_class.id  
            students = Student.objects.filter(
                school=school,
                class_level=selected_class.name,
                is_active=True,
            ).order_by('gender', 'first_name', 'last_name')
        except ClassLevel.DoesNotExist:
            pass

    # ---------- Save (POST) ----------
    if request.method == 'POST' and students:
        saved = 0
        for s in students:
            status = request.POST.get(f'status_{s.id}')
            if status in ('P', 'A', 'L', 'E'):
                Attendance.objects.update_or_create(
                    student=s,
                    date=selected_date,
                    defaults={
                        'status': status,
                        'recorded_by': request.user,
                    }
                )
                saved += 1

        messages.success(
            request,
            f'Attendance saved for {saved} student{"s" if saved != 1 else ""} on {selected_date.strftime("%d %b %Y")}.'
        )
        return redirect(f'/dashboard/teacher/attendance/?class={class_id}&date={selected_date.strftime("%Y-%m-%d")}')

    # ---------- Build rows ----------
    if students:
        existing = Attendance.objects.filter(
            student__in=students,
            date=selected_date,
        ).values_list('student_id', 'status')
        status_map = dict(existing)

        for s in students:
            rows.append({
                'student': s,
                'status': status_map.get(s.id, ''),
            })

    # ---------- Summary ----------
    summary = {
        'total': len(students),
        'marked': len([r for r in rows if r['status']]),
        'present': len([r for r in rows if r['status'] == 'P']),
        'absent': len([r for r in rows if r['status'] == 'A']),
        'late': len([r for r in rows if r['status'] == 'L']),
        'excused': len([r for r in rows if r['status'] == 'E']),
    }

    today = date.today()
    yesterday = today - timedelta(days=1)

    return render(request, 'dashboard/teacher_attendance.html', {
        'classes': classes,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'today': today,
        'yesterday': yesterday,
        'rows': rows,
        'summary': summary,
    })


@login_required
@class_teacher_only
def class_teacher_attendance(request):
    """Mark attendance for the class teacher's class."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from datetime import date, datetime
    import json

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        messages.error(request, 'No teacher profile linked to your account.')
        return redirect('dashboard_home')

    if not teacher.current_class:
        messages.warning(request, 'You are not assigned as a class teacher.')
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    today = date.today()

    # Get selected date (default today)
    date_str = request.GET.get('date') or request.POST.get('date') or today.strftime('%Y-%m-%d')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    # Prevent future dates
    if selected_date > today:
        selected_date = today

    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('first_name', 'last_name')
    student_ids = list(students.values_list('id', flat=True))

    # ---------- POST: Save attendance ----------
    if request.method == 'POST':
        saved = 0
        for sid in student_ids:
            status_val = request.POST.get(f'status_{sid}')
            if status_val not in ('P', 'A', 'L', 'E'):
                continue
            Attendance.objects.update_or_create(
                student_id=sid,
                date=selected_date,
                defaults={
                    'status': status_val,
                    'recorded_by': user,
                }
            )
            saved += 1
        messages.success(request, f'✅ Attendance saved for {saved} students.')
        return redirect(f"{reverse('class_teacher_attendance')}?date={selected_date.strftime('%Y-%m-%d')}")

    # ---------- GET: Load existing ----------
    existing = Attendance.objects.filter(
        student_id__in=student_ids,
        date=selected_date,
    ).values_list('student_id', 'status')

    existing_status_map = {str(sid): status for sid, status in existing}
    present_count = sum(1 for _, s in existing if s == 'P')
    absent_count  = sum(1 for _, s in existing if s == 'A')
    late_count    = sum(1 for _, s in existing if s == 'L')

    return render(request, 'dashboard/class_teacher_attendance.html', {
        'teacher': teacher,
        'cls': cls,
        'students': students,
        'total_students': len(student_ids),
        'selected_date': selected_date,
        'today': today,
        'is_today': selected_date == today,
        'existing_status_map': existing_status_map,
        'existing_status_map_json': json.dumps(existing_status_map),
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
    })

    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from django.http import HttpResponse
    from datetime import date, timedelta
    import csv

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    # Date range (default: last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Optional filters
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    if start_str:
        try: start_date = date.fromisoformat(start_str)
        except ValueError: pass
    if end_str:
        try: end_date = date.fromisoformat(end_str)
        except ValueError: pass

    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    student_ids = list(students.values_list('id', flat=True))

    attendance = Attendance.objects.filter(
        student_id__in=student_ids,
        date__gte=start_date,
        date__lte=end_date,
    ).values_list('student_id', 'date', 'status')

    att_map = {}
    for sid, dt, st in attendance:
        att_map.setdefault(sid, {})[dt] = st

    # Build CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_{cls.name.replace(" ", "_")}_'
        f'{start_date.isoformat()}_to_{end_date.isoformat()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Admission No', 'Student Name', 'Class',
        'Present', 'Absent', 'Late', 'Excused',
        'Attendance %', 'Period'
    ])

    for s in students:
        s_att = att_map.get(s.id, {})
        p = sum(1 for v in s_att.values() if v == 'P')
        a = sum(1 for v in s_att.values() if v == 'A')
        l = sum(1 for v in s_att.values() if v == 'L')
        e = sum(1 for v in s_att.values() if v == 'E')
        total = p + a + l + e
        pct = round((p / total) * 100, 1) if total else 0

        writer.writerow([
            s.admission_number,
            s.full_name,
            cls.name,
            p, a, l, e,
            f'{pct}%',
            f'{start_date.isoformat()} to {end_date.isoformat()}',
        ])

    return response


@class_teacher_only
def class_teacher_attendance_sheet(request):
    """Download attendance sheet as CSV for the class."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from django.http import HttpResponse
    from datetime import date, timedelta
    import csv

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    # Date range (default: last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    if start_str:
        try: start_date = date.fromisoformat(start_str)
        except ValueError: pass
    if end_str:
        try: end_date = date.fromisoformat(end_str)
        except ValueError: pass

    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    student_ids = list(students.values_list('id', flat=True))

    attendance = Attendance.objects.filter(
        student_id__in=student_ids,
        date__gte=start_date,
        date__lte=end_date,
    ).values_list('student_id', 'date', 'status')

    att_map = {}
    for sid, dt, st in attendance:
        att_map.setdefault(sid, {})[dt] = st

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_{cls.name.replace(" ", "_")}_'
        f'{start_date.isoformat()}_to_{end_date.isoformat()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'Admission No', 'Student Name', 'Class',
        'Present', 'Absent', 'Late', 'Excused',
        'Attendance %', 'Period'
    ])

    for s in students:
        s_att = att_map.get(s.id, {})
        p = sum(1 for v in s_att.values() if v == 'P')
        a = sum(1 for v in s_att.values() if v == 'A')
        l = sum(1 for v in s_att.values() if v == 'L')
        e = sum(1 for v in s_att.values() if v == 'E')
        total = p + a + l + e
        pct = round((p / total) * 100, 1) if total else 0

        writer.writerow([
            s.admission_number,
            s.full_name,
            cls.name,
            p, a, l, e,
            f'{pct}%',
            f'{start_date.isoformat()} to {end_date.isoformat()}',
        ])

    return response


@login_required
@class_teacher_only
def class_teacher_attendance_pdf(request):
    """Printable A4 attendance sheet PDF."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.attendance.models import Attendance
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from datetime import date, datetime

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class', 'user').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    today = date.today()

    date_str = request.GET.get('date') or today.strftime('%Y-%m-%d')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    # Girls first, then boys
    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('gender', 'first_name', 'last_name')

    student_ids = list(students.values_list('id', flat=True))

    existing = Attendance.objects.filter(
        student_id__in=student_ids, date=selected_date,
    ).values_list('student_id', 'status')
    status_map = dict(existing)

    rows = []
    for i, s in enumerate(students, start=1):
        rows.append({
            'index': i,
            'student': s,
            'status': status_map.get(s.id, ''),
        })

    present = sum(1 for s in status_map.values() if s == 'P')
    absent = sum(1 for s in status_map.values() if s == 'A')
    late = sum(1 for s in status_map.values() if s == 'L')
    excused = sum(1 for s in status_map.values() if s == 'E')
    not_marked = len(student_ids) - len(status_map)

    html_string = render_to_string('pdf/attendance_sheet.html', {
        'school': user.school,
        'cls': cls,
        'teacher': teacher,
        'selected_date': selected_date,
        'rows': rows,
        'present': present,
        'absent': absent,
        'late': late,
        'excused': excused,
        'not_marked': not_marked,
        'total_students': len(student_ids),
        'generated_at': datetime.now(),
        'generated_by': user,
    })

    filename = f"attendance_{cls.name.replace(' ', '_')}_{selected_date.isoformat()}.pdf"
    return html_to_pdf_response(html_string, filename)


@login_required
def admin_attendance_overview(request):
    """School-wide attendance overview for admins."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.attendance.models import Attendance
    from datetime import date, datetime

    school = request.user.school
    today = date.today()

    # Selected date (default today)
    date_str = request.GET.get('date') or today.strftime('%Y-%m-%d')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    if selected_date > today:
        selected_date = today

    # All classes in school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    # All students
    all_students = Student.objects.filter(school=school, is_active=True)
    total_students = all_students.count()

    # Today's attendance
    attendance_qs = Attendance.objects.filter(
        student__school=school,
        date=selected_date,
    ).select_related('student')

    present_count = attendance_qs.filter(status='P').count()
    absent_count = attendance_qs.filter(status='A').count()
    late_count = attendance_qs.filter(status='L').count()
    excused_count = attendance_qs.filter(status='E').count()
    marked_count = attendance_qs.count()
    not_marked = total_students - marked_count

    attendance_pct = round((present_count / total_students) * 100, 1) if total_students else 0

    # Per-class breakdown
    class_rows = []
    for c in classes:
        class_students = all_students.filter(class_level=c.name)
        class_total = class_students.count()
        if class_total == 0:
            continue

        class_attendance = attendance_qs.filter(student__class_level=c.name)
        class_present = class_attendance.filter(status='P').count()
        class_absent = class_attendance.filter(status='A').count()
        class_late = class_attendance.filter(status='L').count()
        class_marked = class_attendance.count()

        if class_marked == 0:
            pct = None
        else:
            pct = round((class_present / class_total) * 100, 1)

        class_rows.append({
            'class': c,
            'total': class_total,
            'present': class_present,
            'absent': class_absent,
            'late': class_late,
            'marked': class_marked,
            'not_marked': class_total - class_marked,
            'pct': pct,
        })

    # Absent students today
    absent_today = attendance_qs.filter(status='A').select_related(
        'student'
    ).order_by('student__class_level', 'student__first_name')

    # Sort class rows: marked first, then by order
    class_rows.sort(key=lambda r: (r['pct'] is None, r['class'].order, r['class'].name))

    return render(request, 'dashboard/admin_attendance_overview.html', {
        'selected_date': selected_date,
        'today': today,
        'is_today': selected_date == today,
        'classes': classes,
        'class_rows': class_rows,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'excused_count': excused_count,
        'marked_count': marked_count,
        'not_marked': not_marked,
        'attendance_pct': attendance_pct,
        'absent_today': absent_today,
    })


@login_required
def admin_class_attendance(request, class_id):
    """Placeholder — will show per-class attendance drill-down."""
    messages.info(request, 'Class-level attendance coming soon.')
    return redirect('admin_attendance_overview')


@login_required
def admin_attendance_export(request):
    """Export school-wide attendance as CSV."""
    if request.user.role not in ('school_admin', 'super_admin'):
        return redirect('dashboard_home')

    from apps.attendance.models import Attendance
    from django.http import HttpResponse
    from datetime import date, datetime
    import csv

    school = request.user.school
    date_str = request.GET.get('date') or date.today().strftime('%Y-%m-%d')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = date.today()

    qs = Attendance.objects.filter(
        student__school=school,
        date=selected_date,
    ).select_related('student').order_by('student__class_level', 'student__first_name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_all_{selected_date.isoformat()}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(['Date', 'Admission No', 'Student Name', 'Class', 'Status'])

    for a in qs:
        writer.writerow([
            selected_date.isoformat(),
            a.student.admission_number,
            a.student.full_name,
            a.student.class_level or '—',
            a.get_status_display(),
        ])

    return response


