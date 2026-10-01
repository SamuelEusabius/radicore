from rest_framework import viewsets
from .models import Exam, Grade
from .serializers import ExamSerializer, GradeSerializer
from apps.accounts.permissions import IsTeacher
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required


class ExamViewSet(viewsets.ModelViewSet):
    serializer_class = ExamSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = Exam.objects.all()
        if user.is_super_admin:
            return qs
        return qs.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)


class GradeViewSet(viewsets.ModelViewSet):
    serializer_class = GradeSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = Grade.objects.select_related('student', 'subject', 'exam')
        if user.is_super_admin:
            return qs
        return qs.filter(student__school=user.school)
    # ==========================================================
# PDF REPORT CARD
# ==========================================================

@login_required
def report_card_pdf(request, student_id, exam_id):
    """Generate a detailed PDF report card with rankings and performance graph."""
    from apps.students.models import Student
    from .models import Exam, Grade
    from .services.report_card import (
        cbc_grade, compute_rankings, subject_positions,
        previous_exam_for, build_performance_chart,
    )
    from apps.core.pdf_utils import html_to_pdf_response
    from django.template.loader import render_to_string

    # Load + authorize
    if request.user.is_super_admin:
        student = get_object_or_404(Student, id=student_id)
        exam    = get_object_or_404(Exam, id=exam_id)
    else:
        student = get_object_or_404(Student, id=student_id, school=request.user.school)
        exam    = get_object_or_404(Exam, id=exam_id, school=request.user.school)

    # Class roster (for ranking)
    from apps.students.models import Student as StudentModel
    classmates = StudentModel.objects.filter(
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

    # Rankings + positions
    rankings = compute_rankings(exam, classmates)
    class_rank_info = rankings.get(student.id, {'rank': '—', 'total': total_marks, 'avg': avg_pct})
    class_size = classmates.count()

    positions = subject_positions(exam, classmates)

    # Previous exam for comparison
    prev_exam = previous_exam_for(exam, student.school)
    previous_grades_map = {}
    if prev_exam:
        prev_qs = Grade.objects.filter(student=student, exam=prev_exam)
        previous_grades_map = {
            g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
            for g in prev_qs
        }

    # Current grades map for chart
    current_grades_map = {
        g.subject.name: round((float(g.marks) / float(g.out_of or 100)) * 100, 1)
        for g in current_grades
    }

    # Build chart
        # Build chart ONLY if there's a previous exam to compare
    chart_path = None
    if prev_exam and previous_grades_map:
        chart_path = build_performance_chart(current_grades_map, previous_grades_map)

    # Build grade rows with position + CBC grade
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

    # Teacher remarks — optional, from query or default
    teacher_remarks = request.GET.get('remarks', '').strip()

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
        'teacher_remarks': teacher_remarks,
        'school': student.school,
        'user': request.user,
    })

    filename = f'report_{student.admission_number}_{exam.name.replace(" ", "_")}.pdf'
    return html_to_pdf_response(html_string, filename)