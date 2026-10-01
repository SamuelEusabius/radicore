"""
SMART ALERTS ENGINE
Rule-based detection of suspicious patterns.
Runs on-demand or via Celery tasks.
"""

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count

from ..models import Alert


# ==========================================================
# HELPER — create or dedupe an alert
# ==========================================================

def create_alert(school, rule_code, severity, category, title, description,
                 related_object_type='', related_object_id=None, metadata=None):
    """
    Create an alert — but skip if an identical UNRESOLVED alert already exists.
    """
    existing = Alert.objects.filter(
        school=school,
        rule_code=rule_code,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        status__in=[Alert.Status.NEW, Alert.Status.REVIEWING],
    ).exists()

    if existing:
        return None

    return Alert.objects.create(
        school=school,
        rule_code=rule_code,
        severity=severity,
        category=category,
        title=title,
        description=description,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        metadata=metadata or {},
    )


# ==========================================================
# RULE 1 — Duplicate M-Pesa references
# ==========================================================

def detect_duplicate_references(school=None):
    """
    Find payments that share the same reference — either duplicates
    or a sign of manipulation.
    """
    from apps.finance.models import Payment
    from django.db.models import Count

    qs = Payment.objects.values('reference').annotate(
        cnt=Count('id')
    ).filter(cnt__gt=1)

    alerts_created = 0
    for row in qs:
        ref = row['reference']
        payments = Payment.objects.filter(reference=ref)
        school_obj = payments.first().invoice.student.school

        if school and school_obj != school:
            continue

        alert = create_alert(
            school=school_obj,
            rule_code='duplicate_reference',
            severity=Alert.Severity.CRITICAL,
            category=Alert.Category.FRAUD,
            title=f'Duplicate payment reference: {ref}',
            description=(
                f'{payments.count()} payments share the same reference "{ref}". '
                f'This may indicate a duplicate entry or a fraudulent record.'
            ),
            related_object_type='Payment',
            related_object_id=payments.first().id,
            metadata={'reference': ref, 'count': payments.count()},
        )
        if alert:
            alerts_created += 1

    return alerts_created


# ==========================================================
# RULE 2 — Payment amount mismatch
# ==========================================================

def detect_payment_amount_mismatch(school=None):
    """
    Find payments where amount_paid exceeds invoice total,
    or where a payment creates a negative balance.
    """
    from apps.finance.models import Invoice

    qs = Invoice.objects.all()
    if school:
        qs = qs.filter(student__school=school)

    alerts_created = 0
    for invoice in qs:
        if invoice.amount_paid > invoice.amount_due:
            alert = create_alert(
                school=invoice.student.school,
                rule_code='overpayment',
                severity=Alert.Severity.MEDIUM,
                category=Alert.Category.FINANCIAL,
                title=f'Overpayment on invoice #{invoice.id}',
                description=(
                    f'{invoice.student.full_name} has overpaid by '
                    f'KES {float(invoice.amount_paid - invoice.amount_due):,.2f}.'
                ),
                related_object_type='Invoice',
                related_object_id=invoice.id,
                metadata={
                    'amount_due': float(invoice.amount_due),
                    'amount_paid': float(invoice.amount_paid),
                },
            )
            if alert:
                alerts_created += 1

    return alerts_created


# ==========================================================
# RULE 3 — Duplicate students (same name + DOB)
# ==========================================================

def detect_duplicate_students(school=None):
    """Find students with the same first+last name and DOB."""
    from apps.students.models import Student

    qs = Student.objects.filter(is_active=True)
    if school:
        qs = qs.filter(school=school)

    seen = {}
    alerts_created = 0

    for s in qs:
        key = (s.school_id, s.first_name.lower(), s.last_name.lower(), str(s.date_of_birth or ''))
        if key in seen:
            # Duplicate found
            first = seen[key]
            alert = create_alert(
                school=s.school,
                rule_code='duplicate_student',
                severity=Alert.Severity.MEDIUM,
                category=Alert.Category.DUPLICATE,
                title=f'Possible duplicate student: {s.full_name}',
                description=(
                    f'Two students share the same name and DOB: '
                    f'{first.admission_number} and {s.admission_number}. '
                    f'Please verify.'
                ),
                related_object_type='Student',
                related_object_id=s.id,
                metadata={'other_admission': first.admission_number},
            )
            if alert:
                alerts_created += 1
        else:
            seen[key] = s

    return alerts_created


# ==========================================================
# RULE 4 — Overdue invoices > 30 days
# ==========================================================

def detect_overdue_invoices(school=None):
    """Find invoices overdue by more than 30 days."""
    from apps.finance.models import Invoice

    cutoff = timezone.now().date() - timedelta(days=30)
    qs = Invoice.objects.filter(
        due_date__lt=cutoff,
        status__in=['unpaid', 'partial', 'overdue'],
    )
    if school:
        qs = qs.filter(student__school=school)

    alerts_created = 0
    for inv in qs[:50]:  # limit
        alert = create_alert(
            school=inv.student.school,
            rule_code='overdue_30d',
            severity=Alert.Severity.MEDIUM,
            category=Alert.Category.FINANCIAL,
            title=f'Invoice #{inv.id} overdue 30+ days',
            description=(
                f'{inv.student.full_name} owes KES {float(inv.balance):,.2f} '
                f'as of {inv.due_date}.'
            ),
            related_object_type='Invoice',
            related_object_id=inv.id,
            metadata={'balance': float(inv.balance)},
        )
        if alert:
            alerts_created += 1

    return alerts_created


# ==========================================================
# RULE 5 — Subscription expiring soon
# ==========================================================

def detect_subscription_expiry():
    """Alert for subscriptions expiring within 7 days."""
    from apps.schools.models import SchoolSubscription

    cutoff = timezone.now() + timedelta(days=7)
    qs = SchoolSubscription.objects.filter(
        status__in=['trial', 'active'],
    )

    alerts_created = 0
    for sub in qs:
        if sub.status == 'trial' and sub.trial_ends_at and sub.trial_ends_at <= cutoff:
            alert = create_alert(
                school=sub.school,
                rule_code='trial_expiring',
                severity=Alert.Severity.LOW,
                category=Alert.Category.SUBSCRIPTION,
                title=f'Trial expiring for {sub.school.name}',
                description=(
                    f'Trial expires on {sub.trial_ends_at.strftime("%d %b %Y")}. '
                    f'{sub.days_remaining} days remaining.'
                ),
                related_object_type='SchoolSubscription',
                related_object_id=sub.id,
            )
            if alert:
                alerts_created += 1

        elif sub.status == 'active' and sub.paid_until and sub.paid_until <= cutoff:
            alert = create_alert(
                school=sub.school,
                rule_code='subscription_expiring',
                severity=Alert.Severity.MEDIUM,
                category=Alert.Category.SUBSCRIPTION,
                title=f'Subscription expiring for {sub.school.name}',
                description=(
                    f'Subscription expires on {sub.paid_until.strftime("%d %b %Y")}.'
                ),
                related_object_type='SchoolSubscription',
                related_object_id=sub.id,
            )
            if alert:
                alerts_created += 1

    return alerts_created


# ==========================================================
# RUN ALL RULES
# ==========================================================

def run_all_detections(school=None):
    """Run every detection rule. Returns total alerts created."""
    total = 0
    total += detect_duplicate_references(school)
    total += detect_payment_amount_mismatch(school)
    total += detect_duplicate_students(school)
    total += detect_overdue_invoices(school)
    total += detect_subscription_expiry()
    return total