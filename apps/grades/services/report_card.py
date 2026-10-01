"""
Report card generation service.

Generates:
- Class ranking for a given exam
- Subject position per subject
- Previous term comparison
- Performance line graph (matplotlib → PNG)
"""
from io import BytesIO
from decimal import Decimal


def cbc_grade(pct):
    """Return CBC grade from percentage."""
    if pct >= 80: return 'EE'
    if pct >= 65: return 'ME'
    if pct >= 50: return 'AE'
    return 'BE'


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

    # Aggregate per student
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
        prev = None
        rank = 0
        positions = {}
        for i, (sid, m) in enumerate(entries, start=1):
            if m != prev:
                rank = i
                prev = m
            positions[sid] = rank
        result[sub_id] = positions

    return result


def previous_exam_for(exam, school):
    """
    Returns the most recent exam before the given one (for the same school).
    Compares by year, then by id.
    """
    from apps.grades.models import Exam

    prior = (
        Exam.objects
        .filter(school=school)
        .exclude(id=exam.id)
        .filter(
            # same year + earlier id, OR earlier year
            models_q_prior(exam)
        )
        .order_by('-year', '-id')
        .first()
    )
    return prior


def models_q_prior(exam):
    """Django Q for 'exams before this one'."""
    from django.db.models import Q
    return (
        Q(year__lt=exam.year) |
        Q(year=exam.year, id__lt=exam.id)
    )


def build_performance_chart(current_grades, previous_grades):
    """
    Builds a matplotlib line chart as PNG bytes.

    current_grades / previous_grades:
      dict: {subject_name: percentage}
    """
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt

    subject_names = sorted(set(current_grades.keys()) | set(previous_grades.keys()))
    if not subject_names:
        return None

    curr_vals = [current_grades.get(s, 0) for s in subject_names]
    prev_vals = [previous_grades.get(s, 0) for s in subject_names]

    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=110)

    x = range(len(subject_names))

    # Previous (dashed, grey)
    if previous_grades:
        ax.plot(x, prev_vals, marker='o', linestyle='--',
                color='#94a3b8', linewidth=1.8, markersize=5,
                label='Previous Exam')

    # Current (solid, brand teal)
    ax.plot(x, curr_vals, marker='o', linestyle='-',
            color='#00695c', linewidth=2.2, markersize=7,
            label='Current Exam')

    # Annotate current values
    for i, v in enumerate(curr_vals):
        ax.annotate(f'{int(v)}', (i, v), textcoords='offset points',
                    xytext=(0, 8), ha='center', fontsize=8, color='#00695c')

    ax.set_xticks(list(x))
    ax.set_xticklabels(subject_names, fontsize=8.5, rotation=0)
    ax.set_ylim(0, 100)
    ax.set_ylabel('Percentage (%)', fontsize=8.5, color='#4b5563')
    ax.grid(axis='y', linestyle=':', color='#e5e7eb', linewidth=0.8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#d1d5db')
    ax.spines['bottom'].set_color('#d1d5db')
    ax.tick_params(axis='both', colors='#4b5563', labelsize=8.5)
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)

    import base64
    return base64.b64encode(buf.read()).decode('ascii')