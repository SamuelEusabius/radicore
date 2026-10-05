"""
Notify accountant when a payment lands unallocated.
"""
from apps.notifications.models import Notification


def notify_accountant_of_unallocated(unallocated):
    """Alert all accountants at the school about an unallocated payment."""
    from apps.accounts.models import User

    accountants = User.objects.filter(
        school=unallocated.school,
        role='accountant',
        is_active=True,
    )

    for acc in accountants:
        Notification.objects.create(
            recipient=acc,
            channel='in_app',
            title=f'⚠️ Unallocated payment: KES {unallocated.amount:,.0f}',
            message=(
                f'A payment of KES {unallocated.amount:,.0f} from '
                f'{unallocated.phone} could not be matched to a student. '
                f'Reference: "{unallocated.account_reference or "(blank)"}". '
                f'Please reconcile in the Unallocated Payments queue.'
            ),
        )