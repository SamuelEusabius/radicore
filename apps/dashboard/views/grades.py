"""
Grades & Exams views:
- Exam management
- Grade entry (regular + class-teacher)
- Class results (view + PDF)
- Class teacher rankings (view + download)
- Report cards (single, ZIP, merged PDF)
- Rankings helpers
"""
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Count, Sum, Avg
from .teachers import _ct_teacher_and_class

from apps.accounts.decorators import (
    role_required, school_staff_only, teacher_only,
    class_teacher_only,
)

@login_required
def manage_exams(request):
    if request.user.role not in ('teacher', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.grades.models import Exam

    if request.method == 'POST':
        name = request.POST.get('name')
        term = request.POST.get('term')
        year = request.POST.get('year')
        if name and term and year:
            Exam.objects.get_or_create(
                school=request.user.school, name=name, term=term, year=year
            )
            messages.success(request, f'Exam "{name}" created.')
        return redirect('manage_exams')

    exams = Exam.objects.filter(school=request.user.school).order_by('-year', '-id')
    return render(request, 'dashboard/manage_exams.html', {'exams': exams})


@login_required
def enter_grades(request):
    if request.user.role not in ('teacher', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.grades.models import Exam, Grade
    from apps.academics.models import Subject
    from apps.students.models import Student

    school = request.user.school
    exams = Exam.objects.filter(school=school).order_by('-year', '-id')
    subjects = Subject.objects.filter(school=school)
    students = Student.objects.filter(school=school, is_active=True)

    exam_id = request.GET.get('exam')
    subject_id = request.GET.get('subject')

    selected_exam = None
    selected_subject = None
    rows = []

    if exam_id and subject_id:
        try:
            selected_exam = Exam.objects.get(id=exam_id, school=school)
            selected_subject = Subject.objects.get(id=subject_id, school=school)

            existing = {g.student_id: g for g in Grade.objects.filter(
                exam=selected_exam, subject=selected_subject
            )}

            rows = [{
                'student': s,
                'marks': existing[s.id].marks if s.id in existing else '',
                'out_of': existing[s.id].out_of if s.id in existing else 100,
                'remarks': existing[s.id].remarks if s.id in existing else '',
            } for s in students]

            if request.method == 'POST':
                saved = 0
                for s in students:
                    marks = request.POST.get(f'marks_{s.id}', '').strip()
                    if not marks:
                        continue
                    try:
                        marks_val = float(marks)
                    except ValueError:
                        continue

                    Grade.objects.update_or_create(
                        exam=selected_exam, subject=selected_subject, student=s,
                        defaults={
                            'marks': marks_val,
                            'out_of': float(request.POST.get(f'out_of_{s.id}', 100) or 100),
                            'remarks': request.POST.get(f'remarks_{s.id}', ''),
                        })
                    saved += 1

                messages.success(request, f'{saved} grades saved.')
                return redirect(f'/dashboard/grades/enter/?exam={exam_id}&subject={subject_id}')

        except (Exam.DoesNotExist, Subject.DoesNotExist):
            messages.error(request, 'Invalid exam or subject.')

    return render(request, 'dashboard/enter_grades.html', {
        'exams': exams,
        'subjects': subjects,
        'rows': rows,
        'selected_exam': selected_exam,
        'selected_subject': selected_subject,
    })


@login_required
@login_required
def class_results(request):
    if request.user.role not in ('teacher', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student

    user = request.user
    school = user.school

    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    exams = Exam.objects.filter(school=school).order_by('-year', '-id')

    class_id = request.GET.get('class')
    exam_id = request.GET.get('exam')

    selected_class = None
    selected_exam = None
    results = []

    if not class_id and classes.exists():
        class_id = classes.first().id
    if not exam_id and exams.exists():
        exam_id = exams.first().id

    if class_id and exam_id:
        try:
            selected_class = ClassLevel.objects.get(id=class_id, school=school)
            selected_exam = Exam.objects.get(id=exam_id, school=school)
        except (ClassLevel.DoesNotExist, Exam.DoesNotExist):
            pass

    if selected_class and selected_exam:
        students = Student.objects.filter(
            school=school,
            class_level=selected_class.name,
            is_active=True,
        )

        grades_qs = Grade.objects.filter(
            exam=selected_exam,
            student__in=students,
        ).select_related('subject', 'student')

        student_data = {}
        for g in grades_qs:
            sid = g.student_id
            if sid not in student_data:
                student_data[sid] = {
                    'student': g.student,
                    'marks': 0,
                    'out_of': 0,
                    'subjects': [],
                }
            student_data[sid]['marks'] += float(g.marks)
            student_data[sid]['out_of'] += float(g.out_of)
            student_data[sid]['subjects'].append(g)

        for sid, data in student_data.items():
            if data['out_of'] > 0:
                data['avg'] = round((data['marks'] / data['out_of']) * 100, 1)
            else:
                data['avg'] = 0

            avg = data['avg']
            if avg >= 80:
                data['cbc'] = 'EE'
                data['cbc_label'] = 'Exceeding Expectation'
            elif avg >= 65:
                data['cbc'] = 'ME'
                data['cbc_label'] = 'Meeting Expectation'
            elif avg >= 50:
                data['cbc'] = 'AE'
                data['cbc_label'] = 'Approaching Expectation'
            else:
                data['cbc'] = 'BE'
                data['cbc_label'] = 'Below Expectation'

        results = sorted(student_data.values(), key=lambda x: x['avg'], reverse=True)

        total = len(results)
        for i, r in enumerate(results, start=1):
            r['position'] = i
            r['out_of_total'] = total
                # ---------- Add stats for the redesigned template ----------
    total_students = len(results)
    class_average = round(
        sum(r['avg'] for r in results) / total_students, 1
    ) if total_students else 0
    top_score = max((r['avg'] for r in results), default=0)

    # Collect all subjects present
    all_subjects = set()
    for r in results:
        for g in r.get('subjects', []):
            all_subjects.add(g.subject.name)
    subject_count = len(all_subjects)

    # Add class_teacher name for the header
    class_teacher_name = None
    try:
        from apps.teachers.models import Teacher
        ct = Teacher.objects.filter(
            school=school,
            current_class=selected_class,
            is_class_teacher=True,
            is_active=True,
        ).select_related('user').first()
        if ct:
            class_teacher_name = ct.user.get_full_name or ct.user.email
    except Exception:
        pass

    return render(request, 'dashboard/class_results.html', {
        'classes': classes,
        'exams': exams,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': total_students,
        'class_average': class_average,
        'top_score': top_score,
        'subject_count': subject_count,
        'class_teacher_name': class_teacher_name,
    })

    return render(request, 'dashboard/class_results.html', {
        'classes': classes,
        'exams': exams,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': len(results),
    })


@login_required
def class_results_pdf(request):
    if request.user.role not in ('teacher', 'principal', 'super_admin'):
        return redirect('dashboard_home')

    from apps.academics.models import ClassLevel
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    user = request.user
    school = user.school

    class_id = request.GET.get('class')
    exam_id = request.GET.get('exam')

    try:
        selected_class = ClassLevel.objects.get(id=class_id, school=school)
        selected_exam = Exam.objects.get(id=exam_id, school=school)
    except (ClassLevel.DoesNotExist, Exam.DoesNotExist):
        messages.error(request, 'Invalid class or exam.')
        return redirect('class_results')

    students = Student.objects.filter(
        school=school, class_level=selected_class.name, is_active=True
    )

    grades_qs = Grade.objects.filter(
        exam=selected_exam, student__in=students
    ).select_related('subject', 'student')

    student_data = {}
    for g in grades_qs:
        sid = g.student_id
        if sid not in student_data:
            student_data[sid] = {'student': g.student, 'marks': 0, 'out_of': 0}
        student_data[sid]['marks'] += float(g.marks)
        student_data[sid]['out_of'] += float(g.out_of)

    for sid, data in student_data.items():
        if data['out_of'] > 0:
            data['avg'] = round((data['marks'] / data['out_of']) * 100, 1)
        else:
            data['avg'] = 0
        avg = data['avg']
        if avg >= 80:
            data['cbc'] = 'EE'
        elif avg >= 65:
            data['cbc'] = 'ME'
        elif avg >= 50:
            data['cbc'] = 'AE'
        else:
            data['cbc'] = 'BE'

    results = sorted(student_data.values(), key=lambda x: x['avg'], reverse=True)
    total = len(results)
    for i, r in enumerate(results, start=1):
        r['position'] = i
        r['out_of_total'] = total

    class_teacher = Teacher.objects.filter(
        school=school, current_class=selected_class, is_class_teacher=True,
    ).select_related('user').first()

    html_string = render_to_string('pdf/class_results.html', {
        'school': school,
        'selected_class': selected_class,
        'selected_exam': selected_exam,
        'results': results,
        'total_students': total,
        'class_teacher': class_teacher,
        'user': user,
    })

    filename = f'class_results_{selected_class.name}_{selected_exam.name}.pdf'
    return html_to_pdf_response(html_string, filename)


@login_required
@class_teacher_only
def class_teacher_grades(request):
    """Excel-style grades entry for the class teacher's class."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade
    from apps.academics.models import Subject
    from django.utils import timezone
    import json

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        messages.error(request, 'No teacher profile linked to your account.')
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class

    exams = Exam.objects.filter(school=user.school).order_by('-year', '-id')

    # ---------- POST: Save grades ----------
    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        payload_str = request.POST.get('payload', '[]')
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            messages.error(request, 'Exam not found.')
            return redirect('class_teacher_grades')

        try:
            rows = json.loads(payload_str)
        except (ValueError, TypeError):
            rows = []

        saved = 0
        for row in rows:
            sid = row.get('student_id')
            sub_id = row.get('subject_id')
            marks = row.get('marks')
            if not (sid and sub_id):
                continue
            try:
                marks_val = float(marks)
            except (ValueError, TypeError):
                continue
            if marks_val < 0 or marks_val > 100:
                continue

            Grade.objects.update_or_create(
                exam=exam,
                student_id=sid,
                subject_id=sub_id,
                defaults={'marks': marks_val, 'out_of': 100},
            )
            saved += 1

        messages.success(request, f'✅ {saved} grades saved for {exam.name}.')
        return redirect(f"{reverse('class_teacher_grades')}?exam={exam.id}")

    # ---------- GET: Load grid ----------
    exam_id = request.GET.get('exam')
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            exam = None

    # Students in class
    students = Student.objects.filter(
        school=user.school,
        class_level=cls.name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    student_ids = list(students.values_list('id', flat=True))

    # Subjects (all school subjects — teacher filters on the UI)
    subjects = Subject.objects.filter(school=user.school).order_by('name')
    subjects_json = json.dumps([{'id': s.id, 'name': s.name} for s in subjects])

    # Existing marks for this exam
    existing_marks = {}
    if exam:
        grades = Grade.objects.filter(
            exam=exam, student_id__in=student_ids
        ).values_list('student_id', 'subject_id', 'marks')
        for sid, sub_id, marks in grades:
            existing_marks.setdefault(str(sid), {})[str(sub_id)] = float(marks)

    return render(request, 'dashboard/class_teacher_grades.html', {
        'teacher': teacher,
        'cls': cls,
        'exams': exams,
        'exam': exam,
        'students': students,
        'subjects': subjects,
        'subjects_json': subjects_json,
        'existing_marks_json': json.dumps(existing_marks),
        'current_year': timezone.now().year,
    })


@login_required
@class_teacher_only
def class_teacher_new_exam(request):
    """Create a new exam quickly from grades page."""
    if request.method != 'POST':
        return redirect('class_teacher_grades')

    from apps.grades.models import Exam
    from django.utils import timezone

    name = request.POST.get('name', '').strip()
    term = request.POST.get('term', 'Term 1').strip()
    year = request.POST.get('year') or timezone.now().year

    if not name:
        messages.error(request, 'Exam name is required.')
        return redirect('class_teacher_grades')

    try:
        year = int(year)
    except (ValueError, TypeError):
        year = timezone.now().year

    exam = Exam.objects.create(
        school=request.user.school,
        name=name,
        term=term,
        year=year,
    )
    messages.success(request, f'✅ Exam "{exam.name}" created.')
    return redirect(f"{reverse('class_teacher_grades')}?exam={exam.id}")


@login_required
@class_teacher_only
def class_teacher_rankings(request):
    """Rankings table for the class, per exam."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade

    user = request.user
    try:
        teacher = Teacher.objects.select_related('current_class').get(user=user)
    except Teacher.DoesNotExist:
        return redirect('dashboard_home')

    if not teacher.current_class:
        return redirect('class_teacher_dashboard')

    cls = teacher.current_class
    exams = Exam.objects.filter(school=user.school).order_by('-year', '-id')

    exam_id = request.GET.get('exam')
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=user.school)
        except Exam.DoesNotExist:
            pass
    if not exam and exams.exists():
        exam = exams.first()

    subjects = []
    rankings = []

    if exam:
        students = Student.objects.filter(
            school=user.school, class_level=cls.name, is_active=True,
        ).order_by('first_name', 'last_name')
        student_ids = list(students.values_list('id', flat=True))

        grades = Grade.objects.filter(
            exam=exam, student_id__in=student_ids
        ).select_related('subject')

        # Subjects present
        sub_map = {}
        for g in grades:
            sub_map[g.subject_id] = g.subject
        subjects = sorted(sub_map.values(), key=lambda s: s.name)

        # Marks per student
        by_student = {}
        for g in grades:
            by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

        # Build rankings
        rows = []
        for s in students:
            s_marks = by_student.get(s.id, {})
            marks_list = [s_marks.get(sub.id) for sub in subjects]
            total = sum(m for m in marks_list if m is not None)
            avg = round(total / len(subjects), 1) if subjects else 0
            rows.append({
                'student': s,
                'marks': marks_list,
                'total': total,
                'average': avg,
            })

        # Sort by average desc, assign rank
        rows.sort(key=lambda r: r['average'], reverse=True)
        prev_avg = None
        rank = 0
        for i, r in enumerate(rows, start=1):
            if r['average'] != prev_avg:
                rank = i
                prev_avg = r['average']
            r['rank'] = rank
        rankings = rows

    return render(request, 'dashboard/class_teacher_rankings.html', {
        'teacher': teacher,
        'cls': cls,
        'exams': exams,
        'exam': exam,
        'subjects': subjects,
        'rankings': rankings,
    })


@login_required
@class_teacher_only
def class_teacher_rankings_download(request):
    """Download rankings as CSV."""
    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.grades.models import Exam, Grade
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
    exam_id = request.GET.get('exam')

    try:
        exam = Exam.objects.get(id=exam_id, school=user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        messages.error(request, 'Select an exam first.')
        return redirect('class_teacher_rankings')

    students = Student.objects.filter(
        school=user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')
    student_ids = list(students.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).select_related('subject')

    sub_map = {}
    for g in grades:
        sub_map[g.subject_id] = g.subject
    subjects = sorted(sub_map.values(), key=lambda s: s.name)

    by_student = {}
    for g in grades:
        by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

    rows = []
    for s in students:
        s_marks = by_student.get(s.id, {})
        marks_list = [s_marks.get(sub.id) for sub in subjects]
        total = sum(m for m in marks_list if m is not None)
        avg = round(total / len(subjects), 1) if subjects else 0
        rows.append({
            'student': s,
            'marks': marks_list,
            'total': total,
            'average': avg,
        })

    rows.sort(key=lambda r: r['average'], reverse=True)
    prev_avg = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['average'] != prev_avg:
            rank = i
            prev_avg = r['average']
        r['rank'] = rank

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="rankings_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.csv"'
    )

    writer = csv.writer(response)
    header = ['Rank', 'Admission No', 'Student Name']
    header += [s.name for s in subjects]
    header += ['Total', 'Average %']
    writer.writerow(header)

    for r in rows:
        row = [r['rank'], r['student'].admission_number, r['student'].full_name]
        row += ['' if m is None else m for m in r['marks']]
        row += [r['total'], f"{r['average']}%"]
        writer.writerow(row)

    return response


def _ct_build_rankings(exam, cls, students, subjects):
    """Build the ranking rows used by results sheet + rankings page."""
    from apps.grades.models import Grade
    student_ids = list(students.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).select_related('subject')

    sub_map = {}
    for g in grades:
        sub_map[g.subject_id] = g.subject
    subjects = sorted(sub_map.values(), key=lambda s: s.name)

    by_student = {}
    for g in grades:
        by_student.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

    rows = []
    for s in students:
        s_marks = by_student.get(s.id, {})
        marks_list = [s_marks.get(sub.id) for sub in subjects]
        total = sum(m for m in marks_list if m is not None)
        avg = round(total / len(subjects), 1) if subjects else 0

        def cbc(p):
            if p >= 80: return 'EE'
            if p >= 65: return 'ME'
            if p >= 50: return 'AE'
            return 'BE'

        rows.append({
            'student': s,
            'marks': marks_list,
            'total': total,
            'average': avg,
            'grade': cbc(avg),
        })

    rows.sort(key=lambda r: r['average'], reverse=True)
    prev_avg = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['average'] != prev_avg:
            rank = i
            prev_avg = r['average']
        r['rank'] = rank

    return rows, subjects


@login_required
@class_teacher_only
def class_teacher_results_sheet_pdf(request):
    """Printable A4 landscape class results sheet (CBC)."""
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student
    from apps.academics.models import Subject
    from apps.core.pdf_utils import html_to_pdf_response, image_to_base64
    from apps.grades.services.report_card import (
        cbc_grade, cbc_points, compute_rankings, subject_positions,
    )
    from django.template.loader import render_to_string

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exams = Exam.objects.filter(school=request.user.school).order_by('-year', '-id')
    exam_id = request.GET.get('exam')

    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=request.user.school)
        except Exam.DoesNotExist:
            pass
    if not exam and exams.exists():
        exam = exams.first()

    if not exam:
        return HttpResponse('<h1>No exam selected</h1>', status=404)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    # Subjects present in this exam for this class
    subject_ids = Grade.objects.filter(
        exam=exam, student__in=students
    ).values_list('subject_id', flat=True).distinct()

    subjects = list(
        Subject.objects.filter(id__in=subject_ids).order_by('name')
    )
    if not subjects:
        subjects = list(Subject.objects.filter(school=request.user.school).order_by('name'))

    # Marks matrix
    all_grades = Grade.objects.filter(
        exam=exam, student__in=students
    ).values('student_id', 'subject_id', 'marks', 'out_of')

    marks_matrix = {}
    for g in all_grades:
        sid = g['student_id']
        sub_id = g['subject_id']
        pct = (float(g['marks']) / float(g['out_of'] or 100)) * 100
        marks_matrix.setdefault(sid, {})[sub_id] = round(pct, 1)

    rankings = compute_rankings(exam, students)

    rows = []
    for s in students:
        r = rankings.get(s.id, {'total': 0, 'avg': 0, 'rank': '—'})
        subject_cells = []
        for sub in subjects:
            pct = marks_matrix.get(s.id, {}).get(sub.id)
            subject_cells.append({
                'subject': sub.name,
                'pct': pct if pct is not None else None,
                'grade': cbc_grade(pct) if pct is not None else '—',
            })

        rows.append({
            'student': s,
            'subject_cells': subject_cells,
            'total': r['total'],
            'avg': r['avg'],
            'rank': r['rank'],
            'grade': cbc_grade(r['avg']),
            'points': cbc_points(r['avg']),
        })

    rows.sort(key=lambda x: x['rank'] if isinstance(x['rank'], int) else 999)

    # Class averages
    class_avg = round(sum(r['avg'] for r in rows) / len(rows), 1) if rows else 0

    school_logo_b64 = image_to_base64(request.user.school.logo) if request.user.school.logo else None

    html_string = render_to_string('pdf/class_results.html', {
        'exam': exam,
        'class_level': cls,
        'subjects': subjects,
        'rows': rows,
        'school': request.user.school,
        'user': request.user,
        'school_logo_b64': school_logo_b64,
    })

    filename = f"results_{cls.name.replace(' ', '_')}_{exam.name.replace(' ', '_')}.pdf"
    return html_to_pdf_response(html_string, filename)

@login_required
@class_teacher_only
def class_teacher_all_report_cards_zip(request):
    """ZIP of all report card PDFs for the class (single exam)."""
    from apps.grades.models import Exam
    from apps.students.models import Student
    from apps.grades.services.report_card import (
        cbc_grade, compute_rankings, subject_positions,
        previous_exam_for, build_performance_chart,
    )
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from xhtml2pdf import pisa
    from io import BytesIO
    import zipfile
    from django.utils import timezone

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exam_id = request.GET.get('exam')
    try:
        exam = Exam.objects.get(id=exam_id, school=request.user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        return HttpResponse('<h1>Select an exam</h1>', status=400)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    # Prep rankings/positions once
    classmates = students
    rankings = compute_rankings(exam, classmates)
    positions = subject_positions(exam, classmates)
    class_size = classmates.count()

    # Buffer ZIP in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student in students:
            pdf_bytes = _render_report_card_pdf(
                request, student, exam, rankings, positions, class_size
            )
            if pdf_bytes:
                fname = f"report_{student.admission_number}_{student.full_name.replace(' ', '_')}.pdf"
                zf.writestr(fname, pdf_bytes)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="report_cards_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.zip"'
    )
    return response


@login_required
@class_teacher_only
def class_teacher_all_report_cards_merged(request):
    """Single PDF merging all report cards for the class."""
    from apps.grades.models import Exam
    from apps.students.models import Student
    from apps.grades.services.report_card import (
        compute_rankings, subject_positions,
    )
    from django.http import HttpResponse
    from io import BytesIO
    from pypdf import PdfWriter, PdfReader
    from django.utils import timezone

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exam_id = request.GET.get('exam')
    try:
        exam = Exam.objects.get(id=exam_id, school=request.user.school)
    except (Exam.DoesNotExist, TypeError, ValueError):
        return HttpResponse('<h1>Select an exam</h1>', status=400)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    classmates = students
    rankings = compute_rankings(exam, classmates)
    positions = subject_positions(exam, classmates)
    class_size = classmates.count()

    writer = PdfWriter()
    for student in students:
        pdf_bytes = _render_report_card_pdf(
            request, student, exam, rankings, positions, class_size
        )
        if pdf_bytes:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    out.seek(0)

    response = HttpResponse(out.read(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="report_cards_all_{cls.name.replace(" ", "_")}_'
        f'{exam.name.replace(" ", "_")}.pdf"'
    )
    return response


def _render_report_card_pdf(request, student, exam, rankings, positions, class_size):
    """Helper — returns PDF bytes for a single student's report card, or None."""
    from apps.grades.models import Grade
    from apps.grades.services.report_card import (
        cbc_grade, previous_exam_for, build_performance_chart,
    )
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from io import BytesIO
    from django.utils import timezone

    current_grades = list(
        Grade.objects.filter(student=student, exam=exam)
        .select_related('subject').order_by('subject__name')
    )
    if not current_grades:
        return None  # skip students with no grades for this exam

    total_marks = sum(float(g.marks) for g in current_grades)
    total_out_of = sum(float(g.out_of) for g in current_grades) or 1
    avg_pct = round((total_marks / total_out_of) * 100, 1) if current_grades else 0

    class_rank_info = rankings.get(student.id, {'rank': '—', 'total': total_marks, 'avg': avg_pct})

    # Previous exam + chart
    prev_exam = previous_exam_for(exam, student.school)
    previous_grades_map = {}
    if prev_exam:
        prev_qs = Grade.objects.filter(student=student, exam=prev_exam)
        previous_grades_map = {
            g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
            for g in prev_qs
        }

    current_grades_map = {
        g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        for g in current_grades
    }

    chart_path = None
    if prev_exam and previous_grades_map:
        chart_path = build_performance_chart(current_grades_map, previous_grades_map)

    grade_rows = []
    for g in current_grades:
        pct = round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        pos = positions.get(g.subject_id, {}).get(student.id, '—')
        grade_rows.append({
            'subject': g.subject.name,
            'marks': g.marks,
            'out_of': g.out_of,
            'pct': pct,
            'grade': cbc_grade(pct),
            'position': pos,
        })

    overall_grade = cbc_grade(avg_pct)

    html_string = render_to_string('pdf/report_card.html', {
        'student': student,
        'exam': exam,
        'prev_exam': prev_exam,
        'grade_rows': grade_rows,
        'avg_pct': avg_pct,
        'overall_grade': overall_grade,
        'class_rank': class_rank_info['rank'],
        'class_size': class_size,
        'total_marks': total_marks,
        'total_out_of': total_out_of,
        'chart_path': chart_path,
        'teacher_remarks': '',
        'school': student.school,
        'user': request.user,
    })

    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(src=html_string, dest=buffer, encoding='utf-8')
    if pisa_status.err:
        return None
    return buffer.getvalue()


@login_required
@class_teacher_only
def class_teacher_results_sheet_pdf(request):
    """Printable A4 landscape class results sheet (CBC)."""
    from apps.grades.models import Exam, Grade
    from apps.students.models import Student
    from apps.academics.models import Subject
    from apps.core.pdf_utils import html_to_pdf_response, image_to_base64
    from apps.grades.services.report_card import (
        cbc_grade, cbc_points, compute_rankings,
    )
    from django.template.loader import render_to_string

    teacher, cls = _ct_teacher_and_class(request)
    if teacher is None:
        return redirect('dashboard_home')
    if cls is None:
        return redirect('class_teacher_dashboard')

    exams = Exam.objects.filter(school=request.user.school).order_by('-year', '-id')
    exam_id = request.GET.get('exam')

    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id, school=request.user.school)
        except Exam.DoesNotExist:
            pass
    if not exam and exams.exists():
        exam = exams.first()

    if not exam:
        return HttpResponse('<h1>No exam selected</h1>', status=404)

    students = Student.objects.filter(
        school=request.user.school, class_level=cls.name, is_active=True,
    ).order_by('first_name', 'last_name')

    # Get subjects that have marks for this exam + class
    subject_ids = Grade.objects.filter(
        exam=exam, student__in=students
    ).values_list('subject_id', flat=True).distinct()

    subjects = list(
        Subject.objects.filter(id__in=subject_ids).order_by('name')
    )
    if not subjects:
        subjects = list(Subject.objects.filter(school=request.user.school).order_by('name'))

    # Marks matrix: {student_id: {subject_id: pct}}
    all_grades = Grade.objects.filter(
        exam=exam, student__in=students
    ).values('student_id', 'subject_id', 'marks', 'out_of')

    marks_matrix = {}
    for g in all_grades:
        sid = g['student_id']
        sub_id = g['subject_id']
        pct = (float(g['marks']) / float(g['out_of'] or 100)) * 100
        marks_matrix.setdefault(sid, {})[sub_id] = round(pct, 1)

    rankings = compute_rankings(exam, students)

    rows = []
    for s in students:
        r = rankings.get(s.id, {'total': 0, 'avg': 0, 'rank': '—'})
        subject_cells = []
        for sub in subjects:
            pct = marks_matrix.get(s.id, {}).get(sub.id)
            subject_cells.append({
                'subject': sub.name,
                'pct': pct if pct is not None else None,
                'grade': cbc_grade(pct) if pct is not None else '—',
            })

        rows.append({
            'student': s,
            'subject_cells': subject_cells,
            'total': r['total'],
            'avg': r['avg'],
            'rank': r['rank'],
            'grade': cbc_grade(r['avg']),
            'points': cbc_points(r['avg']),
        })

    rows.sort(key=lambda x: x['rank'] if isinstance(x['rank'], int) else 999)

    # Class average
    class_avg = round(sum(r['avg'] for r in rows) / len(rows), 1) if rows else 0

    school_logo_b64 = image_to_base64(request.user.school.logo) if request.user.school.logo else None

    html_string = render_to_string('pdf/class_results.html', {
        'exam': exam,
        'class_level': cls,
        'subjects': subjects,
        'rows': rows,
        'school': request.user.school,
        'user': request.user,
        'school_logo_b64': school_logo_b64,
    })

    filename = f"results_{cls.name.replace(' ', '_')}_{exam.name.replace(' ', '_')}.pdf"
    return html_to_pdf_response(html_string, filename)



# ============================================================
# CLASS TEACHER HELPERS
# ============================================================

def _ct_teacher_and_class(request):
    """Return (teacher, class_level) for the requesting class teacher."""
    from apps.teachers.models import Teacher

    try:
        teacher = Teacher.objects.select_related('current_class').get(
            user=request.user
        )
    except Teacher.DoesNotExist:
        return None, None

    if not teacher.is_class_teacher or not teacher.current_class:
        return teacher, None

    return teacher, teacher.current_class