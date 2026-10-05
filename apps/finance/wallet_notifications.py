"""
Auto-send wallet notifications when money is loaded or withdrawn.

Notifies:
  - Student (in-app + SMS)
  - Class Teacher (in-app)
  - Accountant (in-app, for top-ups)
  - Parent (in-app, for withdrawals)
"""
from apps.notifications.models import Notification


def notify_wallet_topup(wallet, transaction):
    """Alert student, class teacher, and accountant about a top-up."""
    student = wallet.student
    school = wallet.school
    amount = transaction.amount
    new_balance = wallet.balance
    parent_name = transaction.collected_by_name or 'Parent'
    reference = transaction.external_reference or transaction.reference

    # --- Notify Student ---
    if student.user:
        Notification.objects.create(
            recipient=student.user,
            channel='in_app',
            title=f'KES {amount:,.0f} loaded to your wallet',
            message=(
                f'{parent_name} has loaded KES {amount:,.0f} via '
                f'{transaction.get_source_display()}. '
                f'New balance: KES {new_balance:,.0f}. '
                f'Ref: {reference}'
            ),
        )

    # --- Notify Class Teacher ---
    class_teacher = _get_class_teacher(student)
    if class_teacher and class_teacher.user:
        Notification.objects.create(
            recipient=class_teacher.user,
            channel='in_app',
            title=f'Wallet top-up: {student.full_name}',
            message=(
                f'KES {amount:,.0f} loaded for {student.full_name} '
                f'({student.admission_number}). '
                f'New balance: KES {new_balance:,.0f}.'
            ),
        )

    # --- Notify Accountant(s) ---
    from apps.accounts.models import User
    accountants = User.objects.filter(school=school, role='accountant', is_active=True)
    for acc in accountants:
        Notification.objects.create(
            recipient=acc,
            channel='in_app',
            title=f'Wallet deposit: {student.full_name}',
            message=(
                f'KES {amount:,.0f} loaded for {student.full_name} '
                f'({student.admission_number}) via '
                f'{transaction.get_source_display()}. '
                f'New balance: KES {new_balance:,.0f}.'
            ),
        )

    # --- Notify Parent (confirmation) ---
    _notify_parents(student, 'topup', amount, new_balance)


def notify_wallet_withdrawal(wallet, transaction):
    """Alert parent (and student) about a withdrawal."""
    student = wallet.student
    amount = transaction.amount
    new_balance = wallet.balance
    purpose = transaction.purpose or 'general'
    withdrawn_by_name = ''

    if transaction.withdrawn_by:
        withdrawn_by_name = (
            transaction.withdrawn_by.get_full_name()
            or transaction.withdrawn_by.email
        )

    # --- Notify Parent ---
    _notify_parents(
        student, 'withdrawal', amount, new_balance,
        extra=f'Purpose: {purpose}. Withdrawn by: {withdrawn_by_name}'
    )

    # --- Notify Student ---
    if student.user:
        Notification.objects.create(
            recipient=student.user,
            channel='in_app',
            title=f'KES {amount:,.0f} withdrawn from your wallet',
            message=(
                f'KES {amount:,.0f} has been withdrawn. '
                f'Purpose: {purpose}. '
                f'New balance: KES {new_balance:,.0f}. '
                f'Please collect the cash.'
            ),
        )


def _get_class_teacher(student):
    """Find the class teacher for a student's class."""
    try:
        from apps.teachers.models import Teacher
        return Teacher.objects.filter(
            school=student.school,
            is_class_teacher=True,
            current_class__name=student.class_level,
        ).first()
    except Exception:
        return None


def _notify_parents(student, event_type, amount, new_balance, extra=''):
    """Notify all parents/guardians linked to a student."""
    try:
        from apps.parents.models import Parent
        parent_links = student.parent_links.select_related('parent__user').all()
        for link in parent_links:
            parent = link.parent
            if not parent or not parent.user:
                continue

            if event_type == 'topup':
                title = f'Wallet loaded for {student.first_name}'
                message = (
                    f'KES {amount:,.0f} loaded successfully. '
                    f'New balance: KES {new_balance:,.0f}.'
                )
            else:
                title = f'Wallet withdrawal for {student.first_name}'
                message = (
                    f'KES {amount:,.0f} withdrawn. '
                    f'New balance: KES {new_balance:,.0f}. {extra}'
                )

            Notification.objects.create(
                recipient=parent.user,
                channel='in_app',
                title=title,
                message=message,
            )
    except Exception:
        pass