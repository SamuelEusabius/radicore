"""
CBC Performance Level grading system — Kenya Competency-Based Curriculum.
Point scale: 1 (lowest) to 8 (highest).
"""

CBC_GRADES = [
    {'level': 'EE1', 'label': 'Exceeding Expectation 1', 'min': 90, 'max': 99, 'points': 8, 'category': 'exceeding'},
    {'level': 'EE2', 'label': 'Exceeding Expectation 2', 'min': 75, 'max': 89, 'points': 7, 'category': 'exceeding'},
    {'level': 'ME1', 'label': 'Meeting Expectation 1', 'min': 58, 'max': 74, 'points': 6, 'category': 'meeting'},
    {'level': 'ME2', 'label': 'Meeting Expectation 2', 'min': 41, 'max': 57, 'points': 5, 'category': 'meeting'},
    {'level': 'AE1', 'label': 'Approaching Expectation 1', 'min': 31, 'max': 40, 'points': 4, 'category': 'approaching'},
    {'level': 'AE2', 'label': 'Approaching Expectation 2', 'min': 21, 'max': 30, 'points': 3, 'category': 'approaching'},
    {'level': 'BE1', 'label': 'Below Expectation 1', 'min': 11, 'max': 20, 'points': 2, 'category': 'below'},
    {'level': 'BE2', 'label': 'Below Expectation 2', 'min': 1, 'max': 10, 'points': 1, 'category': 'below'},
]


def compute_grade(marks, out_of=100):
    """Convert raw marks to CBC level + points (1-8)."""
    if marks is None:
        return {'level': '—', 'label': 'Not Graded', 'points': 0, 'category': 'none'}

    try:
        marks = float(marks)
        out_of = float(out_of) if out_of else 100
        if out_of <= 0:
            out_of = 100
        # Normalize to percentage
        pct = (marks / out_of) * 100
    except (ValueError, TypeError):
        return {'level': '—', 'label': 'Invalid', 'points': 0, 'category': 'none'}

    # Clamp
    pct = max(0, min(100, pct))

    # Exact match first
    for grade in CBC_GRADES:
        if grade['min'] <= pct <= grade['max']:
            return dict(grade)

    # Edge cases
    if pct == 0:
        return {'level': 'BE2', 'label': 'Below Expectation 2', 'points': 1, 'category': 'below'}
    if pct == 100:
        return {'level': 'EE1', 'label': 'Exceeding Expectation 1', 'points': 8, 'category': 'exceeding'}

    # Fallback
    if pct >= 90:
        return dict(CBC_GRADES[0])
    if pct >= 75:
        return dict(CBC_GRADES[1])
    if pct >= 58:
        return dict(CBC_GRADES[2])
    if pct >= 41:
        return dict(CBC_GRADES[3])
    if pct >= 31:
        return dict(CBC_GRADES[4])
    if pct >= 21:
        return dict(CBC_GRADES[5])
    if pct >= 11:
        return dict(CBC_GRADES[6])
    return dict(CBC_GRADES[7])


def points_to_overall_grade(avg_points):
    """Given average points (1-8), return overall CBC level."""
    if avg_points >= 7.5:
        return 'EE1'
    if avg_points >= 6.5:
        return 'EE2'
    if avg_points >= 5.5:
        return 'ME1'
    if avg_points >= 4.5:
        return 'ME2'
    if avg_points >= 3.5:
        return 'AE1'
    if avg_points >= 2.5:
        return 'AE2'
    if avg_points >= 1.5:
        return 'BE1'
    return 'BE2'


def grade_color(category):
    """CSS color for a grade category."""
    return {
        'exceeding': '#059669',
        'meeting': '#2563eb',
        'approaching': '#d97706',
        'below': '#dc2626',
        'none': '#6b7280',
    }.get(category, '#6b7280')


def generate_teacher_remark(student, avg_points, class_rank, class_size, subjects_data, prev_avg_points=None):
    """Auto-generate class teacher's remark."""
    name = student.first_name or "The learner"

    # Base statement
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

    # Weak subjects
    weak_subjects = [
        s['subject'] for s in subjects_data
        if s['points'] <= 3
    ]
    if weak_subjects:
        subs = ', '.join(weak_subjects[:3])
        base += f" Should focus more on {subs}."

    # Rank info
    if class_rank == 1:
        base += " Ranked 1st in class."
    elif class_rank <= 3:
        base += f" Ranked {class_rank} out of {class_size}."
    elif class_rank <= class_size * 0.5:
        base += f" Ranked {class_rank}/{class_size} — above average."
    else:
        base += f" Ranked {class_rank}/{class_size} — needs improvement."

    # Improvement
    if prev_avg_points is not None:
        if avg_points > prev_avg_points + 0.5:
            base += " Showed improvement from the previous exam."
        elif avg_points < prev_avg_points - 0.5:
            base += " Performance declined slightly from the previous exam."

    return base


def generate_principal_remark(avg_points, class_rank, class_size, prev_avg_points=None):
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


def get_grade_choices():
    """Return choices for forms."""
    return [(g['level'], f"{g['level']} — {g['label']} ({g['min']}–{g['max']})") for g in CBC_GRADES]