"""
Director of Studies — academic analytics dashboard.
School-wide visibility across classes, subjects, exams, teachers.
"""
from datetime import date, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.utils import timezone

from apps.accounts.models import User


def _dos_required(request):
    """DOS or School Admin can access."""
    return request.user.role in ('director_of_studies', 'principal')


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def dos_dashboard(request):
    """DOS main dashboard — whole-school academic overview."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Exam, Grade
    from apps.attendance.models import Attendance

    school = request.user.school
    today = date.today()

    # --- Counts ---
    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_teachers = Teacher.objects.filter(school=school, is_active=True).count()
    total_classes = ClassLevel.objects.filter(school=school).count()
    total_subjects = Subject.objects.filter(school=school).count()

    # Streams — class_level field with same level but diff streams
    # Since we don't have a Stream model, we derive from distinct class_level names
    streams = Student.objects.filter(
        school=school, is_active=True
    ).values_list('class_level', flat=True).distinct().exclude(class_level='')
    total_streams = len(set(streams))

    # --- Exams ---
    total_exams = Exam.objects.filter(school=school).count()

    # --- Academic performance ---
    all_grades = Grade.objects.filter(
        student__school=school
    )
    if all_grades.exists():
        avg_pct = all_grades.aggregate(
            avg_pct=Avg('marks')
        )['avg_pct'] or 0
        avg_performance = round(float(avg_pct), 1)
    else:
        avg_performance = 0

    # --- Attendance ---
    this_week_start = today - timedelta(days=7)
    attendance_qs = Attendance.objects.filter(
        student__school=school,
        date__gte=this_week_start,
    )
    total_attendance_marked = attendance_qs.count()
    present_count = attendance_qs.filter(status='P').count()
    attendance_pct = (
        round((present_count / total_attendance_marked) * 100, 1)
        if total_attendance_marked else 0
    )

    # --- Top/bottom subjects by mean score ---
    subject_stats = []
    for sub in Subject.objects.filter(school=school):
        grades = Grade.objects.filter(
            student__school=school, subject=sub
        )
        if grades.exists():
            mean = grades.aggregate(m=Avg('marks'))['m'] or 0
            subject_stats.append({
                'subject': sub,
                'mean': round(float(mean), 1),
                'count': grades.count(),
            })
    subject_stats.sort(key=lambda x: x['mean'], reverse=True)

    # --- Recent exams ---
    recent_exams = Exam.objects.filter(school=school).order_by('-year', '-id')[:5]

    # --- Class performance summary ---
    class_stats = []
    for cls in ClassLevel.objects.filter(school=school):
        students_in_class = Student.objects.filter(
            school=school, class_level=cls.name, is_active=True
        )
        grades = Grade.objects.filter(student__in=students_in_class)
        if grades.exists():
            mean = grades.aggregate(m=Avg('marks'))['m'] or 0
            class_stats.append({
                'cls': cls,
                'student_count': students_in_class.count(),
                'mean': round(float(mean), 1),
            })

    return render(request, 'dashboard/dos/dashboard.html', {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'total_streams': total_streams,
        'total_subjects': total_subjects,
        'total_exams': total_exams,
        'avg_performance': avg_performance,
        'attendance_pct': attendance_pct,
        'subject_stats': subject_stats[:8],
        'class_stats': class_stats,
        'recent_exams': recent_exams,
        'today': today,
    })


# ============================================================
# CLASSES + STREAMS
# ============================================================

@login_required
def dos_classes(request):
    """List all classes with student counts and performance."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel
    from apps.grades.models import Grade

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    class_rows = []
    for cls in classes:
        students = Student.objects.filter(
            school=school, class_level=cls.name, is_active=True
        )
        grades = Grade.objects.filter(student__in=students)

        mean = grades.aggregate(m=Avg('marks'))['m'] if grades.exists() else 0
        student_count = students.count()

        # Class teacher
        class_teacher = None
        try:
            from apps.teachers.models import Teacher
            class_teacher = Teacher.objects.filter(
                school=school,
                is_class_teacher=True,
                current_class=cls,
            ).first()
        except Exception:
            pass

        class_rows.append({
            'cls': cls,
            'student_count': student_count,
            'mean': round(float(mean), 1) if mean else 0,
            'class_teacher': class_teacher,
        })

    return render(request, 'dashboard/dos/classes.html', {
        'class_rows': class_rows,
    })


@login_required
def dos_class_detail(request, class_id):
    """Detailed view of one class — students, performance, subjects."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    cls = get_object_or_404(ClassLevel, id=class_id, school=school)

    students = Student.objects.filter(
        school=school, class_level=cls.name, is_active=True
    ).order_by('first_name', 'last_name')

    # Exam filter
    exam_id = request.GET.get('exam')
    if exam_id:
        exam = get_object_or_404(Exam, id=exam_id, school=school)
    else:
        exam = Exam.objects.filter(school=school).order_by('-year', '-id').first()

    # Grades for this class + exam
    grade_rows = []
    if exam:
        grades = Grade.objects.filter(
            student__in=students, exam=exam
        ).select_related('subject', 'student')

        by_student = {}
        for g in grades:
            by_student.setdefault(g.student_id, []).append(g)

        for s in students:
            s_grades = by_student.get(s.id, [])
            total = sum(float(g.marks) for g in s_grades)
            count = len(s_grades)
            mean = round(total / count, 1) if count else 0
            grade_rows.append({
                'student': s,
                'total': round(total, 1),
                'mean': mean,
                'subjects_count': count,
            })

        # Sort by mean desc
        grade_rows.sort(key=lambda x: x['mean'], reverse=True)

    # Subject means
    subject_means = []
    if exam:
        for sub in Subject.objects.filter(school=school):
            g = Grade.objects.filter(
                student__in=students, exam=exam, subject=sub
            )
            if g.exists():
                m = g.aggregate(m=Avg('marks'))['m']
                subject_means.append({
                    'subject': sub,
                    'mean': round(float(m), 1),
                    'count': g.count(),
                })
        subject_means.sort(key=lambda x: x['mean'], reverse=True)

    all_exams = Exam.objects.filter(school=school).order_by('-year', '-id')

    return render(request, 'dashboard/dos/class_detail.html', {
        'cls': cls,
        'students': students,
        'grade_rows': grade_rows,
        'subject_means': subject_means,
        'exam': exam,
        'all_exams': all_exams,
        'student_count': students.count(),
    })


# ============================================================
# VIRTUAL CLASS GROUPING (KEY FEATURE)
# ============================================================

@login_required
def dos_combine(request):
    """Combine multiple classes for VIRTUAL analysis (no DB merge) with full analytics."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')
    all_exams = Exam.objects.filter(school=school).order_by('-year', '-id')

    selected_ids = request.GET.getlist('classes')
    exam_id = request.GET.get('exam')

    combined_data = None
    if selected_ids and exam_id:
        try:
            selected_classes = list(ClassLevel.objects.filter(
                id__in=selected_ids, school=school
            ))
            exam = get_object_or_404(Exam, id=exam_id, school=school)

            # All students across selected classes (still in their own class)
            students = list(Student.objects.filter(
                school=school,
                class_level__in=[c.name for c in selected_classes],
                is_active=True,
            ).order_by('first_name', 'last_name'))

            # All subjects
            subjects = list(Subject.objects.filter(school=school).order_by('name'))

            # Get all grades
            grades = Grade.objects.filter(
                student__in=students, exam=exam
            ).select_related('subject', 'student')

            # ---- Grade matrix: {student_id: {subject_id: marks}} ----
            matrix = {}
            for g in grades:
                matrix.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

            # ---- Student rows ----
            student_rows = []
            for s in students:
                s_marks = matrix.get(s.id, {})
                total = sum(s_marks.values())
                count = len(s_marks)
                mean = round(total / count, 1) if count else 0

                # CBC grade
                from apps.grades.services.report_card import cbc_grade
                grade = cbc_grade(mean) if count else '—'

                student_rows.append({
                    'student': s,
                    'marks': [round(s_marks.get(sub.id, 0), 1) if sub.id in s_marks else None
                              for sub in subjects],
                    'total': round(total, 1),
                    'count': count,
                    'mean': mean,
                    'grade': grade,
                    'stream': s.class_level,
                })

            # Rank by mean
            student_rows.sort(key=lambda x: x['mean'], reverse=True)
            for i, row in enumerate(student_rows, 1):
                row['rank'] = i

            # ---- Subject statistics ----
            subject_stats = []
            for idx, sub in enumerate(subjects):
                sub_grades = [g for g in grades if g.subject_id == sub.id]
                if not sub_grades:
                    continue
                marks_list = [float(g.marks) for g in sub_grades]
                mean = round(sum(marks_list) / len(marks_list), 1)
                highest = round(max(marks_list), 1)
                lowest = round(min(marks_list), 1)
                pass_count = sum(1 for m in marks_list if m >= 50)

                # Best student in this subject
                best_grade = max(sub_grades, key=lambda x: float(x.marks))

                subject_stats.append({
                    'subject': sub,
                    'mean': mean,
                    'highest': highest,
                    'lowest': lowest,
                    'count': len(marks_list),
                    'pass_pct': round((pass_count / len(marks_list)) * 100, 1),
                    'best_student': best_grade.student,
                    'best_mark': round(float(best_grade.marks), 1),
                })

            # Sort subjects by mean (best first)
            subject_stats.sort(key=lambda x: x['mean'], reverse=True)

            # ---- Best subject for the exam ----
            best_subject = subject_stats[0] if subject_stats else None

            # ---- Stream comparison ----
            stream_stats = {}
            for row in student_rows:
                stream = row['stream'] or 'Unknown'
                stream_stats.setdefault(stream, []).append(row['mean'])

            stream_comparison = []
            for stream, means in stream_stats.items():
                stream_comparison.append({
                    'stream': stream,
                    'count': len(means),
                    'mean': round(sum(means) / len(means), 1) if means else 0,
                })
            stream_comparison.sort(key=lambda x: x['mean'], reverse=True)

            # ---- Overall stats ----
            all_means = [r['mean'] for r in student_rows if r['mean'] > 0]
            overall_mean = round(sum(all_means) / len(all_means), 1) if all_means else 0

            # ---- Previous exam comparison ----
            prev_exam = Exam.objects.filter(
                school=school
            ).exclude(id=exam.id).order_by('-year', '-id').first()

            trend_data = []
            if prev_exam:
                prev_grades = Grade.objects.filter(
                    student__in=students, exam=prev_exam
                )
                for sub in subjects:
                    curr_sub = [float(g.marks) for g in grades if g.subject_id == sub.id]
                    prev_sub = [float(g.marks) for g in prev_grades if g.subject_id == sub.id]
                    if curr_sub and prev_sub:
                        curr_mean = round(sum(curr_sub) / len(curr_sub), 1)
                        prev_mean = round(sum(prev_sub) / len(prev_sub), 1)
                        diff = round(curr_mean - prev_mean, 1)
                        trend_data.append({
                            'subject': sub,
                            'current': curr_mean,
                            'previous': prev_mean,
                            'diff': diff,
                            'direction': 'up' if diff > 0.5 else ('down' if diff < -0.5 else 'flat'),
                        })

            combined_data = {
                'selected_classes': selected_classes,
                'exam': exam,
                'prev_exam': prev_exam,
                'subjects': subjects,
                'student_rows': student_rows,
                'subject_stats': subject_stats,
                'stream_comparison': stream_comparison,
                'best_subject': best_subject,
                'overall_mean': overall_mean,
                'students_count': len(students),
                'trend_data': trend_data,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error combining: {e}')

        # Save selected classes to session for report card combined ranking
    if combined_data and combined_data.get('selected_classes'):
        request.session['dos_combined_classes'] = [
            c.name for c in combined_data['selected_classes']
        ]
        request.session['dos_combined_exam'] = exam_id

    return render(request, 'dashboard/dos/combine.html', {
        'classes': classes,
        'all_exams': all_exams,
        'selected_ids': [int(i) for i in selected_ids if i.isdigit()],
        'selected_exam': exam_id,
        'combined_data': combined_data,
    })
# ============================================================
# EXAM ANALYTICS
# ============================================================

@login_required
def dos_analytics(request):
    """Analyse any exam — filter by exam + class."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    all_exams = Exam.objects.filter(school=school).order_by('-year', '-id')
    classes = ClassLevel.objects.filter(school=school).order_by('order', 'name')

    exam_id = request.GET.get('exam')
    class_id = request.GET.get('class')

    analytics = None
    if exam_id:
        exam = get_object_or_404(Exam, id=exam_id, school=school)

        students_qs = Student.objects.filter(school=school, is_active=True)
        if class_id:
            cls = get_object_or_404(ClassLevel, id=class_id, school=school)
            students_qs = students_qs.filter(class_level=cls.name)

        grades = Grade.objects.filter(
            student__in=students_qs, exam=exam
        ).select_related('subject', 'student')

        if grades.exists():
            # Overall
            overall_mean = grades.aggregate(m=Avg('marks'))['m'] or 0
            highest = grades.aggregate(h=Max('marks'))['h'] or 0
            lowest = grades.aggregate(l=Min('marks'))['l'] or 0
            total_count = grades.count()
            pass_count = grades.filter(marks__gte=50).count()

            # Grade distribution (using CBC levels)
            from apps.grades.services.report_card import cbc_grade
            dist = {'EE1': 0, 'EE2': 0, 'ME1': 0, 'ME2': 0, 'AE1': 0, 'AE2': 0, 'BE1': 0, 'BE2': 0}
            for g in grades:
                pct = float(g.marks)
                level = cbc_grade(pct)
                if level in dist:
                    dist[level] += 1

            analytics = {
                'exam': exam,
                'overall_mean': round(float(overall_mean), 1),
                'highest': round(float(highest), 1),
                'lowest': round(float(lowest), 1),
                'total_count': total_count,
                'pass_pct': round((pass_count / total_count) * 100, 1) if total_count else 0,
                'distribution': dist,
                'student_count': students_qs.count(),
            }

    return render(request, 'dashboard/dos/analytics.html', {
        'all_exams': all_exams,
        'classes': classes,
        'selected_exam': exam_id,
        'selected_class': class_id,
        'analytics': analytics,
    })


@login_required
def dos_subject_matrix(request):
    """Subject performance matrix across the school."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    all_exams = Exam.objects.filter(school=school).order_by('-year', '-id')
    exam_id = request.GET.get('exam')

    matrix = []
    if exam_id:
        exam = get_object_or_404(Exam, id=exam_id, school=school)
        for sub in Subject.objects.filter(school=school).order_by('name'):
            grades = Grade.objects.filter(subject=sub, exam=exam)
            if not grades.exists():
                continue
            m = grades.aggregate(m=Avg('marks'))['m'] or 0
            hi = grades.aggregate(h=Max('marks'))['h'] or 0
            lo = grades.aggregate(l=Min('marks'))['l'] or 0
            total = grades.count()
            passes = grades.filter(marks__gte=50).count()
            matrix.append({
                'subject': sub,
                'mean': round(float(m), 1),
                'highest': round(float(hi), 1),
                'lowest': round(float(lo), 1),
                'count': total,
                'pass_pct': round((passes / total) * 100, 1) if total else 0,
            })
        matrix.sort(key=lambda x: x['mean'], reverse=True)

    return render(request, 'dashboard/dos/subject_matrix.html', {
        'all_exams': all_exams,
        'selected_exam': exam_id,
        'matrix': matrix,
    })


@login_required
def dos_comparison(request):
    """Compare performance across exams (trend)."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.students.models import Student
    from apps.academics.models import Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    all_exams = Exam.objects.filter(school=school).order_by('year', 'id')

    # Compare top subjects across all exams
    comparison = []
    for sub in Subject.objects.filter(school=school).order_by('name')[:10]:
        row = {'subject': sub, 'exams': []}
        for exam in all_exams:
            g = Grade.objects.filter(subject=sub, exam=exam)
            if g.exists():
                m = g.aggregate(m=Avg('marks'))['m'] or 0
                row['exams'].append({
                    'exam': exam,
                    'mean': round(float(m), 1),
                })
        if row['exams']:
            comparison.append(row)

    return render(request, 'dashboard/dos/comparison.html', {
        'all_exams': all_exams,
        'comparison': comparison,
    })


# ============================================================
# LESSON FOLLOW-UP
# ============================================================

@login_required
def dos_lessons(request):
    """Lesson follow-up — scheduled vs completed."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.teachers.models import Teacher

    school = request.user.school
    teachers = Teacher.objects.filter(
        school=school, is_active=True
    ).select_related('user', 'current_class')

    # Try to import timetable from academics
    TimetableEntry = None
    try:
        from apps.academics.models import Timetable
        TimetableEntry = Timetable
    except ImportError:
        pass

    teacher_rows = []
    for t in teachers:
        lessons_count = 0
        try:
            if TimetableEntry:
                lessons_count = TimetableEntry.objects.filter(
                    teacher=t
                ).count()
        except Exception:
            lessons_count = 0

        teacher_rows.append({
            'teacher': t,
            'scheduled': lessons_count,
            'completed': lessons_count,  
            'missed': 0,
            'completion_pct': 100 if lessons_count else 0,
        })

    return render(request, 'dashboard/dos/lessons.html', {
        'teacher_rows': teacher_rows,
    })

# ============================================================
# TEACHER MONITORING
# ============================================================

@login_required
def dos_teachers(request):
    """Teacher academic overview."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from apps.teachers.models import Teacher
    from apps.students.models import Student
    from apps.academics.models import Subject

    school = request.user.school
    teachers = Teacher.objects.filter(
        school=school, is_active=True
    ).select_related('user', 'current_class')

    teacher_rows = []
    for t in teachers:
        # Try to fetch subjects via t.user (Subject.teacher likely references User)
        subjects_taught = []
        try:
            subjects_taught = list(Subject.objects.filter(
                school=school, teacher=t.user
            ))
        except Exception:
            # Fallback: subjects by school (if teacher FK isn't set)
            try:
                subjects_taught = list(Subject.objects.filter(school=school)[:0])
            except Exception:
                subjects_taught = []

        student_count = 0
        if t.current_class:
            student_count = Student.objects.filter(
                school=school,
                class_level=t.current_class.name,
                is_active=True,
            ).count()

        teacher_rows.append({
            'teacher': t,
            'subjects': subjects_taught,
            'student_count': student_count,
            'is_class_teacher': t.is_class_teacher,
        })

    return render(request, 'dashboard/dos/teachers.html', {
        'teacher_rows': teacher_rows,
    })
# ============================================================
# PDF REPORT
# ============================================================

@login_required
def dos_report_pdf(request):
    """Comprehensive academic report PDF."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from apps.core.pdf_utils import image_to_base64
    from apps.students.models import Student
    from apps.teachers.models import Teacher
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Grade, Exam

    school = request.user.school
    today = date.today()

    # Basic stats
    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_teachers = Teacher.objects.filter(school=school, is_active=True).count()

    # Subject means across all exams
    subject_means = []
    for sub in Subject.objects.filter(school=school):
        g = Grade.objects.filter(student__school=school, subject=sub)
        if g.exists():
            m = g.aggregate(m=Avg('marks'))['m'] or 0
            subject_means.append({
                'subject': sub,
                'mean': round(float(m), 1),
                'count': g.count(),
            })
    subject_means.sort(key=lambda x: x['mean'], reverse=True)

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None

    html_string = render_to_string('dashboard/dos/report_pdf.html', {
        'school': school,
        'today': today,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'subject_means': subject_means,
        'school_logo_b64': school_logo_b64,
        'user': request.user,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="dos_report_{today}.pdf"'
    pisa.CreatePDF(src=html_string, dest=response, encoding='utf-8')
    return response
  
  

@login_required
def dos_combine_pdf(request):
    """PDF export of combined classes results sheet."""
    if not _dos_required(request):
        return redirect('dashboard_home')

    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from xhtml2pdf import pisa
    from apps.core.pdf_utils import image_to_base64
    from apps.students.models import Student
    from apps.academics.models import ClassLevel, Subject
    from apps.grades.models import Grade, Exam
    from apps.grades.services.report_card import cbc_grade
    import io

    school = request.user.school
    selected_ids = request.GET.getlist('classes')
    exam_id = request.GET.get('exam')

    if not selected_ids or not exam_id:
        messages.error(request, 'Please select classes and exam.')
        return redirect('dos_combine')

    selected_classes = list(ClassLevel.objects.filter(id__in=selected_ids, school=school))
    exam = get_object_or_404(Exam, id=exam_id, school=school)

    students = list(Student.objects.filter(
        school=school,
        class_level__in=[c.name for c in selected_classes],
        is_active=True,
    ).order_by('first_name', 'last_name'))

    subjects = list(Subject.objects.filter(school=school).order_by('name'))

    grades = Grade.objects.filter(
        student__in=students, exam=exam
    ).select_related('subject', 'student')

    # Matrix
    matrix = {}
    for g in grades:
        matrix.setdefault(g.student_id, {})[g.subject_id] = float(g.marks)

    # Student rows
    student_rows = []
    for s in students:
        s_marks = matrix.get(s.id, {})
        total = sum(s_marks.values())
        count = len(s_marks)
        mean = round(total / count, 1) if count else 0
        grade = cbc_grade(mean) if count else '—'
        student_rows.append({
            'student': s,
            'marks': [round(s_marks.get(sub.id, 0), 1) if sub.id in s_marks else None
                      for sub in subjects],
            'total': round(total, 1),
            'count': count,
            'mean': mean,
            'grade': grade,
            'stream': s.class_level,
        })
    student_rows.sort(key=lambda x: x['mean'], reverse=True)
    for i, row in enumerate(student_rows, 1):
        row['rank'] = i

    # Subject stats
    subject_stats = []
    for sub in subjects:
        sub_grades = [g for g in grades if g.subject_id == sub.id]
        if not sub_grades:
            continue
        marks_list = [float(g.marks) for g in sub_grades]
        mean = round(sum(marks_list) / len(marks_list), 1)
        highest = round(max(marks_list), 1)
        lowest = round(min(marks_list), 1)
        pass_count = sum(1 for m in marks_list if m >= 50)
        best_grade = max(sub_grades, key=lambda x: float(x.marks))
        subject_stats.append({
            'subject': sub,
            'mean': mean,
            'highest': highest,
            'lowest': lowest,
            'pass_pct': round((pass_count / len(marks_list)) * 100, 1),
            'best_student': best_grade.student,
            'best_mark': round(float(best_grade.marks), 1),
        })
    subject_stats.sort(key=lambda x: x['mean'], reverse=True)

    # Stream comparison
    stream_stats = {}
    for row in student_rows:
        stream = row['stream'] or 'Unknown'
        stream_stats.setdefault(stream, []).append(row['mean'])

    stream_comparison = []
    for stream, means in stream_stats.items():
        stream_comparison.append({
            'stream': stream,
            'count': len(means),
            'mean': round(sum(means) / len(means), 1) if means else 0,
        })
    stream_comparison.sort(key=lambda x: x['mean'], reverse=True)

    all_means = [r['mean'] for r in student_rows if r['mean'] > 0]
    overall_mean = round(sum(all_means) / len(all_means), 1) if all_means else 0

    school_logo_b64 = image_to_base64(school.logo) if school.logo else None
    
    from datetime import date
    today = date.today()

    html_string = render_to_string('dashboard/dos/combine_pdf.html', {
        'school': school,
        'selected_classes': selected_classes,
        'exam': exam,
        'subjects': subjects,
        'student_rows': student_rows,
        'subject_stats': subject_stats,
        'stream_comparison': stream_comparison,
        'overall_mean': overall_mean,
        'students_count': len(students),
        'school_logo_b64': school_logo_b64,
        'today': today,
        'user': request.user,
    })

    response = HttpResponse(content_type='application/pdf')
    cls_names = '_'.join(c.name.replace(' ', '_') for c in selected_classes)
    response['Content-Disposition'] = f'attachment; filename="combined_{cls_names}_{exam.name.replace(" ", "_")}.pdf"'
    pisa.CreatePDF(src=io.StringIO(html_string), dest=response, encoding='utf-8')
    return response