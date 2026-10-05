"""
Report card generation service.

Generates:
- Class ranking for a given exam
- Subject position per subject
- Previous term comparison
- Performance line graph (matplotlib → PNG → base64 data URI)
- CBC Performance Levels (EE1-EE2, ME1-ME2, AE1-AE2, BE1-BE2) with points 1-8
"""
from io import BytesIO
from decimal import Decimal


# ============================================================
# CBC PERFORMANCE LEVELS
# ============================================================

CBC_LEVELS = [
    {'level': 'EE1', 'label': 'Exceeding Expectation 1',   'min': 90, 'max': 100, 'points': 8, 'category': 'exceeding'},
    {'level': 'EE2', 'label': 'Exceeding Expectation 2',   'min': 75, 'max': 89,  'points': 7, 'category': 'exceeding'},
    {'level': 'ME1', 'label': 'Meeting Expectation 1',     'min': 58, 'max': 74,  'points': 6, 'category': 'meeting'},
    {'level': 'ME2', 'label': 'Meeting Expectation 2',     'min': 41, 'max': 57,  'points': 5, 'category': 'meeting'},
    {'level': 'AE1', 'label': 'Approaching Expectation 1', 'min': 31, 'max': 40,  'points': 4, 'category': 'approaching'},
    {'level': 'AE2', 'label': 'Approaching Expectation 2', 'min': 21, 'max': 30,  'points': 3, 'category': 'approaching'},
    {'level': 'BE1', 'label': 'Below Expectation 1',       'min': 11, 'max': 20,  'points': 2, 'category': 'below'},
    {'level': 'BE2', 'label': 'Below Expectation 2',       'min': 1,  'max': 10,  'points': 1, 'category': 'below'},
]


def cbc_grade(pct):
    """Return CBC Performance Level code based on percentage."""
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return '—'
    if pct >= 100:
        return 'EE1'
    if pct <= 0:
        return 'BE2'
    for level in CBC_LEVELS:
        if level['min'] <= pct <= level['max']:
            return level['level']
    return '—'


def cbc_points(pct):
    """Return CBC points (1-8) based on percentage."""
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return 0
    if pct >= 100:
        return 8
    if pct <= 0:
        return 0
    for level in CBC_LEVELS:
        if level['min'] <= pct <= level['max']:
            return level['points']
    return 0


def cbc_label(pct):
    """Return full CBC label based on percentage."""
    code = cbc_grade(pct)
    for level in CBC_LEVELS:
        if level['level'] == code:
            return level['label']
    return 'Not Graded'


def points_to_overall_grade(avg_points):
    """Given average points (1-8), return the overall CBC level."""
    try:
        avg_points = float(avg_points)
    except (TypeError, ValueError):
        return '—'
    if avg_points >= 7.5: return 'EE1'
    if avg_points >= 6.5: return 'EE2'
    if avg_points >= 5.5: return 'ME1'
    if avg_points >= 4.5: return 'ME2'
    if avg_points >= 3.5: return 'AE1'
    if avg_points >= 2.5: return 'AE2'
    if avg_points >= 1.5: return 'BE1'
    if avg_points >= 0.5: return 'BE2'
    return '—'


# ============================================================
# RANKINGS
# ============================================================

def compute_rankings(exam, students_qs):
    """
    Returns dict: {student_id: {'rank': int, 'total': float, 'avg': float}}
    Rankings by average (descending), ties share rank.
    """
    from apps.grades.models import Grade

    student_ids = list(students_qs.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).values_list('student_id', 'marks', 'out_of')

    totals = {}
    for sid, marks, out_of in grades:
        t = totals.setdefault(sid, {'marks': 0.0, 'out_of': 0.0})
        t['marks'] += float(marks)
        t['out_of'] += float(out_of)

    rows = []
    for sid in student_ids:
        t = totals.get(sid, {'marks': 0.0, 'out_of': 0.0})
        avg = round((t['marks'] / t['out_of']) * 100, 1) if t['out_of'] else 0
        rows.append({'id': sid, 'total': round(t['marks'], 1), 'avg': avg})

    rows.sort(key=lambda r: r['avg'], reverse=True)

    prev = None
    rank = 0
    result = {}
    for i, r in enumerate(rows, start=1):
        if r['avg'] != prev:
            rank = i
            prev = r['avg']
        result[r['id']] = {'rank': rank, 'total': r['total'], 'avg': r['avg']}

    return result


def subject_positions(exam, students_qs):
    """
    Returns dict: {subject_id: {student_id: position}}
    Position per subject within the class.
    """
    from apps.grades.models import Grade

    student_ids = list(students_qs.values_list('id', flat=True))

    grades = Grade.objects.filter(
        exam=exam, student_id__in=student_ids
    ).values_list('subject_id', 'student_id', 'marks')

    by_subject = {}
    for sub_id, sid, marks in grades:
        by_subject.setdefault(sub_id, []).append((sid, float(marks)))

    result = {}
    for sub_id, entries in by_subject.items():
        entries.sort(key=lambda x: x[1], reverse=True)
        result[sub_id] = {sid: idx + 1 for idx, (sid, _) in enumerate(entries)}

    return result


def previous_exam_for(exam, school):
    """Find the previous exam (by date or year/term) for comparison."""
    from apps.grades.models import Exam

    qs = Exam.objects.filter(school=school).exclude(id=exam.id).order_by('-year', '-id')

    if exam.date:
        qs = qs.filter(date__lt=exam.date)

    return qs.first()


# ============================================================
# PERFORMANCE CHART (returns base64 data URI)
# ============================================================

def build_performance_chart(current_grades, previous_grades):
    """
    Builds a matplotlib line chart as a base64 data URI.
    Compatible with xhtml2pdf (no external file needed).

    current_grades / previous_grades: dict {subject_name: percentage}
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    subject_names = sorted(set(current_grades.keys()) | set(previous_grades.keys()))
    if not subject_names:
        return None

    curr_vals = [current_grades.get(s, 0) for s in subject_names]
    prev_vals = [previous_grades.get(s, 0) for s in subject_names]

    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=110)

    x = range(len(subject_names))

    if previous_grades:
        ax.plot(x, prev_vals, marker='o', linestyle='--',
                color='#94a3b8', linewidth=1.8, markersize=5,
                label='Previous Exam')

    ax.plot(x, curr_vals, marker='o', linestyle='-',
            color='#00695c', linewidth=2.2, markersize=7,
            label='Current Exam')

    for i, v in enumerate(curr_vals):
        ax.annotate(f'{int(v)}', (i, v), textcoords='offset points',
                    xytext=(0, 8), ha='center', fontsize=8, color='#00695c')

    ax.set_xticks(list(x))
    ax.set_xticklabels(subject_names, fontsize=8.5, rotation=0)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Percentage (%)', fontsize=9)
    ax.grid(axis='y', linestyle=':', alpha=0.4)
    ax.legend(loc='upper right', fontsize=8, frameon=False)

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)

    plt.tight_layout()

    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    plt.close(fig)

    # Convert to base64 data URI
    import base64
    data = base64.b64encode(buffer.getvalue()).decode('ascii')
    buffer.close()

    return f'data:image/png;base64,{data}'


# ============================================================
# AUTO-GENERATED REMARKS
# ============================================================

def generate_teacher_remark(student, grade_rows, avg_points, class_rank, class_size, prev_avg_points=None):
    """Auto-generate personalized class teacher's remark."""
    name = student.first_name or "The learner"

    if avg_points >= 7:
        base = f"{name} has demonstrated excellent mastery across subjects. An outstanding performance."
    elif avg_points >= 5.5:
        base = f"{name} has met expectations well. Consistent effort is shown."
    elif avg_points >= 4:
        base = f"{name} is approaching expectations. With more focus, improvement is achievable."
    elif avg_points >= 2.5:
        base = f"{name} requires more effort and consistent practice to reach the expected level."
    else:
        base = f"{name} needs significant support and closer monitoring to improve."

    weak_subjects = [r['subject'] for r in grade_rows if r.get('points', 0) <= 3]
    if weak_subjects:
        subs = ', '.join(weak_subjects[:3])
        base += f" Should focus more on {subs}."

    try:
        rank_int = int(class_rank)
        if rank_int == 1:
            base += " Ranked 1st in class."
        elif rank_int <= 3:
            base += f" Ranked {rank_int} out of {class_size}."
        elif rank_int <= class_size * 0.5:
            base += f" Ranked {rank_int}/{class_size} — above average."
        else:
            base += f" Ranked {rank_int}/{class_size} — needs improvement."
    except (ValueError, TypeError):
        pass

    if prev_avg_points is not None:
        if avg_points > prev_avg_points + 0.5:
            base += " Showed improvement from the previous exam."
        elif avg_points < prev_avg_points - 0.5:
            base += " Performance declined slightly from the previous exam."

    return base


def generate_principal_remark(avg_points, prev_avg_points=None):
    """Auto-generate principal's remark."""
    if avg_points >= 7:
        return "Excellent performance. A model student. Keep up the discipline and hard work."
    elif avg_points >= 5.5:
        return "Good progress. Maintain consistency to reach the highest level."
    elif avg_points >= 4:
        return "Fair performance. Focused effort will yield better results."
    elif avg_points >= 2.5:
        return "Requires improvement. Additional support and parental involvement recommended."
    else:
        return "Performance is below expectation. Immediate remedial measures needed."