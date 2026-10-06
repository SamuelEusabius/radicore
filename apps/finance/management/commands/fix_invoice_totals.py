from django.core.management.base import BaseCommand
from django.db.models import Sum
from apps.finance.models import Invoice, Payment


class Command(BaseCommand):
    help = 'Backfill invoice.amount_paid from Payment records'

    def handle(self, *args, **options):
        updated = 0
        for inv in Invoice.objects.all():
            old_paid = inv.amount_paid
            new_paid = Payment.objects.filter(
                invoice_id=inv.id
            ).aggregate(t=Sum('amount_kes'))['t'] or 0

            if float(old_paid) != float(new_paid):
                inv.amount_paid = new_paid
                inv.save(update_fields=['amount_paid'])
                inv.update_status()
                updated += 1
                self.stdout.write(
                    f"Invoice #{inv.id}: {old_paid} → {new_paid} | "
                    f"status → {inv.status}"
                )

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Updated {updated} invoices")
        )