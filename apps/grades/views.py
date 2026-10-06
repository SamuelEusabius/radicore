"""
Grades views — exams, marks entry, report cards.
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from io import BytesIO

from apps.accounts.decorators import role_required
from .models import Exam, Grade
from .services.report_card import (
    cbc_grade,
    cbc_points,
    cbc_label,
    points_to_overall_grade,
    compute_rankings,
    subject_positions,
    previous_exam_for,
    build_performance_chart,
    generate_teacher_remark,
    generate_principal_remark,
)


# ============================================================
# DRF VIEWSETS (for /api/grades/)
# ============================================================

from rest_framework import viewsets, permissions


class ExamViewSet(viewsets.ModelViewSet):
    """API: Manage exams for the current user's school."""
    serializer_class = None  # set below
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_super_admin', False):
            return Exam.objects.all()
        return Exam.objects.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)


class GradeViewSet(viewsets.ModelViewSet):
    """API: Manage grades for the current user's school."""
    serializer_class = None
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_super_admin', False):
            return Grade.objects.all()
        return Grade.objects.filter(student__school=user.school)


# Attach serializers lazily (avoids circular imports)
def _attach_serializers():
    try:
        from .serializers import ExamSerializer, GradeSerializer
        ExamViewSet.serializer_class = ExamSerializer
        GradeViewSet.serializer_class = GradeSerializer
    except Exception:
        pass

_attach_serializers()


# ============================================================
# EXAM MANAGEMENT
# ============================================================

@login_required
@role_required('teacher', 'school_admin')
def class_teacher_all_report_cards_merged(request):
    """Generate one PDF containing report cards for ALL students in a class."""
    from apps.students.models import Student
    from apps.core.pdf_utils import image_to_base64
    from pypdf import PdfWriter, PdfReader
    from xhtml2pdf import pisa

    school = request.user.school
    exam_id = request.GET.get('exam')

    if not exam_id:
        messages.error(request, 'Please select an exam.')
        return redirect('class_results')

    exam = get_object_or_404(Exam, id=exam_id, school=school)

    # Determine the class
    # School admin can pass ?class=<id>; class teacher uses their own class
    class_id = request.GET.get('class')

    if request.user.role == 'school_admin' and class_id:
        from apps.academics.models import ClassLevel
        class_level_obj = get_object_or_404(ClassLevel, id=class_id, school=school)
        class_level_name = class_level_obj.name
    else:
        teacher = getattr(request.user, 'teacher_profile', None)
        if not teacher or not teacher.is_class_teacher or not teacher.current_class:
            messages.error(request, 'You are not assigned to a class.')
            return redirect('class_results')
        class_level_name = teacher.current_class.name

    # Get students
    students = Student.objects.filter(
        school=school,
        class_level=class_level_name,
        is_active=True,
    ).order_by('first_name', 'last_name')

    if not students.exists():
        messages.warning(request, f'No students in {class_level_name}.')
        return redirect('class_results')

    # Preload shared data (school logo, classmates)
    classmates = students
    rankings = compute_rankings(exam, classmates)
    positions = subject_positions(exam, classmates)
    class_size = classmates.count()

    prev_exam = previous_exam_for(exam, school)
    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    # Generate individual PDFs
    writer = PdfWriter()

    for student in students:
        pdf_bytes = _render_single_report_card(
            student=student,
            exam=exam,
            school=school,
            rankings=rankings,
            positions=positions,
            class_size=class_size,
            prev_exam=prev_exam,
            school_logo_b64=school_logo_b64,
            user=request.user,
        )
        if pdf_bytes:
            reader = PdfReader(BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

    if len(writer.pages) == 0:
        messages.error(request, 'No report cards generated.')
        return redirect('class_results')

    # Write merged PDF
    output = BytesIO()
    writer.write(output)
    writer.close()

    pdf_content = output.getvalue()
    output.close()

    filename = f'report_cards_{class_level_name}_{exam.name.replace(" ", "_")}.pdf'.replace(' ', '_')
    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def _render_single_report_card(student, exam, school, rankings, positions, class_size, prev_exam, school_logo_b64, user):
    """Render one student's report card and return raw PDF bytes."""
    from apps.core.pdf_utils import image_to_base64
    from xhtml2pdf import pisa
    from django.template.loader import render_to_string

    current_grades = list(
        Grade.objects.filter(student=student, exam=exam)
        .select_related('subject')
        .order_by('subject__name')
    )

    total_marks = sum(float(g.marks) for g in current_grades)
    total_out_of = sum(float(g.out_of) for g in current_grades) or 1
    avg_pct = round((total_marks / total_out_of) * 100, 1) if current_grades else 0

    class_rank_info = rankings.get(student.id, {'rank': '—', 'total': total_marks, 'avg': avg_pct})

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

    chart_data_uri = None
    if prev_exam and previous_grades_map:
        try:
            chart_data_uri = build_performance_chart(current_grades_map, previous_grades_map)
        except Exception as e:
            print(f"[CHART] Error: {e}")
            chart_data_uri = None
    else:
        print(f"[CHART DEBUG] SKIPPED — prev_exam={bool(prev_exam)} | prev_map empty={not previous_grades_map}")
    print()
    
        # Grade rows
    grade_rows = []
    for g in current_grades:
        pct = round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        pos = positions.get(g.subject_id, {}).get(student.id, '—')

        trend = None
        trend_diff = None
        if prev_exam and g.subject.name in previous_grades_map:
            prev_pct = previous_grades_map[g.subject.name]
            diff = round(pct - prev_pct, 1)
            if diff > 1:
                trend, trend_diff = 'up', f"+{diff}"
            elif diff < -1:
                trend, trend_diff = 'down', f"{diff}"
            else:
                trend, trend_diff = 'flat', "0"

        # Subject teacher
        teacher_name = ''
        if g.subject.teacher:
            teacher_name = (
                g.subject.teacher.get_full_name()
                or g.subject.teacher.email.split('@')[0]
            )

        grade_rows.append({
            'subject': g.subject.name,
            'teacher': teacher_name,
            'marks': g.marks,
            'out_of': g.out_of,
            'pct': pct,
            'grade': cbc_grade(pct),
            'points': cbc_points(pct),
            'position': pos,
            'trend': trend,
            'trend_diff': trend_diff,
        })

    if grade_rows:
        avg_points = round(sum(r['points'] for r in grade_rows) / len(grade_rows), 1)
    else:
        avg_points = 0

    overall_grade = points_to_overall_grade(avg_points)

    prev_avg_points = None
    if prev_exam and previous_grades_map:
        prev_points_list = [cbc_points(p) for p in previous_grades_map.values()]
        if prev_points_list:
            prev_avg_points = sum(prev_points_list) / len(prev_points_list)

    teacher_remarks = generate_teacher_remark(
        student=student,
        grade_rows=grade_rows,
        avg_points=avg_points,
        class_rank=class_rank_info['rank'],
        class_size=class_size,
        prev_avg_points=prev_avg_points,
    )

    principal_remarks = generate_principal_remark(
        avg_points=avg_points,
        prev_avg_points=prev_avg_points,
    )

    student_photo_b64 = image_to_base64(student.photo) if student.photo else None

    html_string = render_to_string('pdf/report_card.html', {
        'student': student,
        'exam': exam,
        'prev_exam': prev_exam,
        'grade_rows': grade_rows,
        'avg_pct': avg_pct,
        'avg_points': avg_points,
        'overall_grade': overall_grade,
        'class_rank': class_rank_info['rank'],
        'class_size': class_size,
        'total_marks': total_marks,
        'total_out_of': total_out_of,
        'chart_data_uri': chart_data_uri,
        'teacher_remarks': teacher_remarks,
        'principal_remarks': principal_remarks,
        'student_photo_b64': student_photo_b64,
        'school_logo_b64': school_logo_b64,
        'school': school,
        'user': user,
    })

    buffer = BytesIO()
    result = pisa.CreatePDF(src=html_string, dest=buffer, encoding='utf-8')

    if result.err:
        buffer.close()
        return None

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


@login_required
@role_required('teacher', 'school_admin')
def enter_grades(request):
    """Enter grades for a class + exam + subject."""
    from apps.students.models import Student
    from apps.academics.models import ClassLevel, Subject

    school = request.user.school

    exam_id = request.GET.get('exam')
    class_id = request.GET.get('class')
    subject_id = request.GET.get('subject')

    exams = Exam.objects.filter(school=school).order_by('-year', '-date')
    classes = ClassLevel.objects.filter(school=school).order_by('name')
    subjects = Subject.objects.filter(school=school).order_by('name')

    students = []
    existing_grades = {}

    if exam_id and class_id and subject_id:
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        class_level = get_object_or_404(ClassLevel, id=class_id, school=school)
        subject = get_object_or_404(Subject, id=subject_id, school=school)

        students = Student.objects.filter(
            school=school, class_level=class_level.name, is_active=True
        ).order_by('first_name', 'last_name')

        existing_qs = Grade.objects.filter(
            exam=exam, subject=subject, student__in=students
        )
        existing_grades = {g.student_id: g for g in existing_qs}

    if request.method == 'POST':
        exam_id = request.POST.get('exam')
        class_id = request.POST.get('class')
        subject_id = request.POST.get('subject')

        if not (exam_id and class_id and subject_id):
            messages.error(request, 'Please select exam, class, and subject.')
            return redirect('enter_grades')

        exam = get_object_or_404(Exam, id=exam_id, school=school)
        class_level = get_object_or_404(ClassLevel, id=class_id, school=school)
        subject = get_object_or_404(Subject, id=subject_id, school=school)

        students = Student.objects.filter(
            school=school, class_level=class_level.name, is_active=True
        )

        saved = 0
        for student in students:
            marks_val = request.POST.get(f'marks_{student.id}', '').strip()
            out_of_val = request.POST.get(f'out_of_{student.id}', '100').strip()

            if not marks_val:
                continue

            try:
                marks = Decimal(marks_val)
                out_of = Decimal(out_of_val) if out_of_val else Decimal('100')

                Grade.objects.update_or_create(
                    exam=exam,
                    student=student,
                    subject=subject,
                    defaults={'marks': marks, 'out_of': out_of},
                )
                saved += 1
            except (ValueError, Decimal.InvalidOperation):
                messages.warning(request, f'Invalid marks for {student.full_name}')
                continue

        messages.success(request, f'{saved} grade(s) saved.')
        return redirect(f'/dashboard/grades/enter/?exam={exam_id}&class={class_id}&subject={subject_id}')

    return render(request, 'dashboard/enter_grades.html', {
        'exams': exams,
        'classes': classes,
        'subjects': subjects,
        'students': students,
        'existing_grades': existing_grades,
        'selected_exam': exam_id,
        'selected_class': class_id,
        'selected_subject': subject_id,
    })


# ============================================================
# REPORT CARD PDF
# ============================================================

@login_required
def report_card_pdf(request, student_id, exam_id):
    """Generate a detailed PDF report card with rankings and performance graph."""
    from apps.students.models import Student
    from apps.core.pdf_utils import html_to_pdf_response, image_to_base64

    # Load + authorize
    if request.user.is_super_admin:
        student = get_object_or_404(Student, id=student_id)
        exam = get_object_or_404(Exam, id=exam_id)
    else:
        student = get_object_or_404(Student, id=student_id, school=request.user.school)
        exam = get_object_or_404(Exam, id=exam_id, school=request.user.school)

    # Class roster
    classmates = Student.objects.filter(
        school=student.school,
        class_level=student.class_level,
        is_active=True,
    )

    # Current grades
    current_grades = list(
        Grade.objects.filter(student=student, exam=exam)
        .select_related('subject')
        .order_by('subject__name')
    )

    total_marks = sum(float(g.marks) for g in current_grades)
    total_out_of = sum(float(g.out_of) for g in current_grades) or 1
    avg_pct = round((total_marks / total_out_of) * 100, 1) if current_grades else 0

        # Rankings
    rankings = compute_rankings(exam, classmates)
    class_rank_info = rankings.get(student.id, {'rank': '—', 'total': total_marks, 'avg': avg_pct})
    class_size = classmates.count()

    positions = subject_positions(exam, classmates)

    # ============ COMBINED RANKING (Optional) ============
    # If DOS has combined streams recently, show the student's rank in combined
    combined_rank = None
    combined_size = 0
    combined_classes = []

    # Try to fetch last DOS combine from session
    dos_combined = request.session.get('dos_combined_classes', [])

    if dos_combined:
        # Combine students from all selected classes
        combined_students = Student.objects.filter(
            school=student.school,
            class_level__in=dos_combined,
            is_active=True,
        )
        combined_size = combined_students.count()

        if combined_size > 0:
            combined_rankings = compute_rankings(exam, combined_students)
            combined_rank = combined_rankings.get(student.id, {}).get('rank', None)
            combined_classes = dos_combined
    # ====================================================

    # Previous exam
    prev_exam = previous_exam_for(exam, student.school)
    previous_grades_map = {}
    if prev_exam:
        prev_qs = Grade.objects.filter(student=student, exam=prev_exam)
        previous_grades_map = {
            g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
            for g in prev_qs
        }

    # Chart
    current_grades_map = {
        g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        for g in current_grades
    }

    chart_data_uri = None
    if prev_exam and previous_grades_map:
        try:
            chart_data_uri = build_performance_chart(current_grades_map, previous_grades_map)
        except Exception:
            chart_data_uri = None

    # Grade rows
    grade_rows = []
    for g in current_grades:
        pct = round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        pos = positions.get(g.subject_id, {}).get(student.id, '—')

        trend = None
        trend_diff = None
        if prev_exam and g.subject.name in previous_grades_map:
            prev_pct = previous_grades_map[g.subject.name]
            diff = round(pct - prev_pct, 1)
            if diff > 1:
                trend, trend_diff = 'up', f"+{diff}"
            elif diff < -1:
                trend, trend_diff = 'down', f"{diff}"
            else:
                trend, trend_diff = 'flat', "0"

        grade_rows.append({
            'subject': g.subject.name,
            'marks': g.marks,
            'out_of': g.out_of,
            'pct': pct,
            'grade': cbc_grade(pct),
            'points': cbc_points(pct),
            'position': pos,
            'trend': trend,
            'trend_diff': trend_diff,
        })

    # Average points
    if grade_rows:
        avg_points = round(sum(r['points'] for r in grade_rows) / len(grade_rows), 1)
    else:
        avg_points = 0

    overall_grade = points_to_overall_grade(avg_points)

    # Previous exam average points
    prev_avg_points = None
    if prev_exam and previous_grades_map:
        prev_points_list = [cbc_points(p) for p in previous_grades_map.values()]
        if prev_points_list:
            prev_avg_points = sum(prev_points_list) / len(prev_points_list)

    # Auto remarks
    teacher_remarks = request.GET.get('remarks', '').strip()
    if not teacher_remarks:
        teacher_remarks = generate_teacher_remark(
            student=student,
            grade_rows=grade_rows,
            avg_points=avg_points,
            class_rank=class_rank_info['rank'],
            class_size=class_size,
            prev_avg_points=prev_avg_points,
        )

    principal_remarks = generate_principal_remark(
        avg_points=avg_points,
        prev_avg_points=prev_avg_points,
    )

    # Images → base64
    student_photo_b64 = image_to_base64(student.photo) if student.photo else None
    school_logo_b64 = image_to_base64(student.school.logo) if (student.school and student.school.logo) else None

    html_string = render_to_string('pdf/report_card.html', {
        'student': student,
        'exam': exam,
        'prev_exam': prev_exam,
        'grade_rows': grade_rows,
        'avg_pct': avg_pct,
        'avg_points': avg_points,
        'overall_grade': overall_grade,
        'class_rank': class_rank_info['rank'],
        'class_size': class_size,
        'combined_rank': combined_rank,
        'combined_size': combined_size,
        'combined_classes': combined_classes,
        'total_marks': total_marks,
        'total_out_of': total_out_of,
        'chart_data_uri': chart_data_uri,
        'teacher_remarks': teacher_remarks,
        'principal_remarks': principal_remarks,
        'student_photo_b64': student_photo_b64,
        'school_logo_b64': school_logo_b64,
        'school': student.school,
        'user': request.user,
    })

    filename = f'report_{student.admission_number}_{exam.name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)


# ============================================================
# CLASS RESULTS
# ============================================================

@login_required
@role_required('teacher', 'school_admin')
def class_results(request):
    from apps.academics.models import ClassLevel
    from apps.students.models import Student

    school = request.user.school

    exam_id = request.GET.get('exam')
    class_id = request.GET.get('class')

    exams = Exam.objects.filter(school=school).order_by('-year', '-date')
    classes = ClassLevel.objects.filter(school=school).order_by('name')

    results = []
    exam = None
    class_level = None

    if exam_id and class_id:
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        class_level = get_object_or_404(ClassLevel, id=class_id, school=school)

        students = Student.objects.filter(
            school=school, class_level=class_level.name, is_active=True
        )

        rankings = compute_rankings(exam, students)

        for s in students:
            r = rankings.get(s.id, {'total': 0, 'avg': 0, 'rank': '—'})
            results.append({
                'student': s,
                'total': r['total'],
                'avg': r['avg'],
                'rank': r['rank'],
                'grade': cbc_grade(r['avg']),
                'points': cbc_points(r['avg']),
            })

        results.sort(key=lambda x: x['rank'] if isinstance(x['rank'], int) else 999)

    return render(request, 'dashboard/class_results.html', {
        'exams': exams,
        'classes': classes,
        'results': results,
        'exam': exam,
        'class_level': class_level,
        'selected_exam': exam_id,
        'selected_class': class_id,
    })


@login_required
@role_required('teacher', 'school_admin')
def class_results_pdf(request):
    """Generate a class results sheet PDF with all students + subjects."""
    from apps.academics.models import ClassLevel, Subject
    from apps.students.models import Student
    from apps.core.pdf_utils import html_to_pdf_response, image_to_base64

    school = request.user.school

    exam_id = request.GET.get('exam')
    class_id = request.GET.get('class')

    if not exam_id or not class_id:
        messages.error(request, 'Please select exam and class.')
        return redirect('class_results')

    exam = get_object_or_404(Exam, id=exam_id, school=school)
    class_level = get_object_or_404(ClassLevel, id=class_id, school=school)

    students = Student.objects.filter(
        school=school, class_level=class_level.name, is_active=True
    ).order_by('first_name', 'last_name')

    # All subjects for the school (or subjects present in the exam)
    subjects = list(
        Subject.objects.filter(
            grades__exam=exam,
            grades__student__in=students,
        ).distinct().order_by('name')
    )

    # If no subjects found, fallback to all school subjects
    if not subjects:
        subjects = list(Subject.objects.filter(school=school).order_by('name'))

    # Build a marks matrix: {student_id: {subject_id: percentage}}
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

    # Build rows
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

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    html_string = render_to_string('pdf/class_results.html', {
        'exam': exam,
        'class_level': class_level,
        'subjects': subjects,
        'rows': rows,
        'school': school,
        'user': request.user,
        'school_logo_b64': school_logo_b64,
    })

    filename = f'results_{class_level.name}_{exam.name.replace(" ", "_")}.pdf'.replace(' ', '_')
    return html_to_pdf_response(html_string, filename)


# ============================================================
# CLASS TEACHER REDIRECTS
# ============================================================

@login_required
@role_required('teacher', 'school_admin')
def class_teacher_grades(request):
    return redirect('enter_grades')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_new_exam(request):
    return redirect('manage_exams')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_rankings(request):
    return redirect('class_results')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_rankings_download(request):
    return redirect('class_results_pdf')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_results_sheet_pdf(request):
    return redirect('class_results_pdf')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_all_report_cards_zip(request):
    messages.info(request, 'Bulk report cards ZIP — coming soon.')
    return redirect('class_results')


@login_required
@role_required('teacher', 'school_admin')
def class_teacher_all_report_cards_merged(request):
    messages.info(request, 'Merged report cards PDF — coming soon.')
    return redirect('class_results')


# ============================================================
# HELPERS
# ============================================================

def _ct_teacher_and_class(request):
    teacher = getattr(request.user, 'teacher_profile', None)
    if not teacher or not teacher.is_class_teacher:
        return None, None
    return teacher, teacher.current_class


def _ct_build_rankings(exam, students_qs):
    return compute_rankings(exam, students_qs)


def _render_report_card_pdf(request, student_id, exam_id):
    return report_card_pdf(request, student_id, exam_id)