from celery import shared_task
from django.utils import timezone
from apps.finance.models import Invoice


@shared_task
def mark_overdue_invoices():
    """Marks all unpaid invoices past their due date as overdue."""
    today = timezone.now().date()
    unpaid = Invoice.objects.filter(status='unpaid', due_date__lt=today)
    
    count = 0
    for inv in unpaid:
        inv.status = 'overdue'
        inv.save(update_fields=['status'])
        count += 1
    
    return f'{count} invoices marked as overdue.'