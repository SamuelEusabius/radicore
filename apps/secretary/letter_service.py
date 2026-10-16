"""
Letter generation service.

Renders letters from templates using Django's template engine,
with placeholders filled from student/guardian context.
"""
import logging
from datetime import date

from django.template import Context, Template
from django.utils import timezone

logger = logging.getLogger(__name__)


# Default templates seeded for new schools
DEFAULT_TEMPLATES = {
    'admission': {
        'name': 'Standard Admission Letter',
        'title': 'LETTER OF ADMISSION',
        'body_template': (
            "Dear {{guardian_name}},\n\n"
            "RE: ADMISSION OF {{student_name}} TO {{school_name}}\n\n"
            "We are pleased to inform you that your child, "
            "{{student_name}}, has been offered admission to "
            "{{school_name}} in {{class_level}} effective "
            "{{admission_date}}.\n\n"
            "Please report to the school on or before the date indicated "
            "above with the following:\n"
            "  1. Birth Certificate (original and copy)\n"
            "  2. Previous school report card / leaving certificate\n"
            "  3. Two passport-size photographs\n"
            "  4. Duly filled medical form\n\n"
            "Fees for the term are payable on or before the reporting date. "
            "Details of the fee structure are available at the accounts office.\n\n"
            "We look forward to welcoming {{student_name}} to our school family."
        ),
        'closing_line': 'Yours faithfully,',
        'signatory_title': 'Principal',
    },
    'transfer': {
        'name': 'Standard Transfer Letter',
        'title': 'TRANSFER LETTER',
        'body_template': (
            "TO WHOM IT MAY CONCERN\n\n"
            "This is to certify that {{student_name}} "
            "(Admission No. {{admission_number}}) was a bonafide student "
            "of {{school_name}} in {{class_level}}.\n\n"
            "Their conduct during the period of study was satisfactory. "
            "They have no outstanding disciplinary or financial obligations "
            "with the school.\n\n"
            "This letter is issued upon request for the purpose of "
            "transfer to another institution. {{reason}}"
        ),
        'closing_line': 'Yours faithfully,',
        'signatory_title': 'Principal',
    },
    'testimonial': {
        'name': 'Standard Testimonial',
        'title': 'TESTIMONIAL',
        'body_template': (
            "This is to certify that {{student_name}} "
            "(Admission No. {{admission_number}}) was a student of "
            "{{school_name}} from {{admission_date}}.\n\n"
            "During their time at our institution, they demonstrated "
            "commitment to academic excellence and participated actively "
            "in co-curricular activities. Their character and conduct "
            "were commendable.\n\n"
            "We wish them success in all their future endeavours."
        ),
        'closing_line': 'Yours faithfully,',
        'signatory_title': 'Principal',
    },
    'recommendation': {
        'name': 'Standard Recommendation',
        'title': 'LETTER OF RECOMMENDATION',
        'body_template': (
            "TO WHOM IT MAY CONCERN\n\n"
            "I am pleased to recommend {{student_name}} "
            "(Admission No. {{admission_number}}) who is a student of "
            "{{class_level}} at {{school_name}}.\n\n"
            "Throughout their tenure at our school, {{student_name}} has "
            "demonstrated strong academic ability, good character, and "
            "a commitment to both curricular and co-curricular excellence. "
            "They relate well with peers and staff alike.\n\n"
            "I have no hesitation in recommending them for any opportunity "
            "they may be seeking."
        ),
        'closing_line': 'Yours faithfully,',
        'signatory_title': 'Principal',
    },
    'good_conduct': {
        'name': 'Certificate of Good Conduct',
        'title': 'CERTIFICATE OF GOOD CONDUCT',
        'body_template': (
            "This is to certify that {{student_name}} "
            "(Admission No. {{admission_number}}) has been a student of "
            "{{school_name}} in {{class_level}}.\n\n"
            "During this period, {{student_name}} maintained exemplary "
            "conduct and discipline, and was never involved in any "
            "disciplinary case.\n\n"
            "This certificate is issued upon request."
        ),
        'closing_line': 'Yours faithfully,',
        'signatory_title': 'Principal',
    },
}


def seed_default_templates(school, created_by=None):
    """
    Create the default letter templates for a school if missing.
    Idempotent — safe to call multiple times.
    """
    from .models import LetterTemplate

    created = 0
    for letter_type, spec in DEFAULT_TEMPLATES.items():
        exists = LetterTemplate.objects.filter(
            school=school, letter_type=letter_type,
            is_default_for_type=True,
        ).exists()
        if exists:
            continue

        LetterTemplate.objects.create(
            school=school,
            letter_type=letter_type,
            name=spec['name'],
            title=spec['title'],
            body_template=spec['body_template'],
            closing_line=spec.get('closing_line', 'Yours faithfully,'),
            signatory_title=spec.get('signatory_title', 'Principal'),
            is_default_for_type=True,
        )
        created += 1
    return created


def render_letter(template_obj, context):
    """
    Renders a letter body/title/closing with the given context dict.
    Supports ---PAGE--- markers for page breaks.
    """
    from django.utils.safestring import mark_safe

    django_context = Context(context)

    title = Template(template_obj.title).render(django_context)
    body = Template(template_obj.body_template).render(django_context)
    closing = Template(template_obj.closing_line or '').render(django_context)
    signatory = template_obj.signatory_name or context.get('principal_name', '')
    signatory_title = Template(template_obj.signatory_title or '').render(django_context)

    # Convert ---PAGE--- markers into page breaks
    if '---PAGE---' in body:
        parts = body.split('---PAGE---')
        html_parts = []
        for i, part in enumerate(parts):
            # Preserve paragraphs inside a page
            block = part.strip()
            block_html = block.replace('\n\n', '</p><p>').replace('\n', '<br>')
            html_parts.append(f'<p>{block_html}</p>')
        body = '<div class="page-break"></div>'.join(html_parts)
        body = mark_safe(body)

    return {
        'title': title.strip(),
        'body': body,
        'closing_line': closing.strip(),
        'signatory_name': signatory.strip(),
        'signatory_title': signatory_title.strip(),
    }


def build_student_context(student, school, reason='', extra=None):
    """
    Builds the placeholder context for a student letter.
    """
    ctx = {
        'student_name': f"{student.first_name} {student.last_name}",
        'admission_number': student.admission_number or '—',
        'class_level': student.class_level or student.cbc_level or '—',
        'admission_date': (
            student.admission_date.strftime('%d %B %Y')
            if student.admission_date else '—'
        ),
        'guardian_name': student.guardian_name or 'Parent/Guardian',
        'school_name': school.name,
        'principal_name': school.principal_name or 'Principal',
        'today': date.today().strftime('%d %B %Y'),
        'reason': reason,
    }
    if extra:
        ctx.update(extra)
    return ctx