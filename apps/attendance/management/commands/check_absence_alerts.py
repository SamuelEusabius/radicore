from django.core.management.base import BaseCommand
from apps.attendance.services.absence_alerts import run_absence_check


class Command(BaseCommand):
    help = 'Scan for 3+ consecutive absence streaks and generate alerts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-id', type=int, default=None,
            help='Only process a specific school ID'
        )
        parser.add_argument(
            '--threshold', type=int, default=3,
            help='Minimum consecutive absent school days to trigger an alert (default 3)'
        )

    def handle(self, *args, **options):
        school_id = options.get('school_id')
        threshold = options.get('threshold', 3)

        school = None
        if school_id:
            from apps.schools.models import School
            school = School.objects.filter(id=school_id).first()
            if not school:
                self.stdout.write(self.style.ERROR(f'School {school_id} not found'))
                return

        self.stdout.write(self.style.WARNING(
            f'\nRunning absence check (threshold={threshold} school days)…\n'
        ))

        summary = run_absence_check(school=school, threshold=threshold)

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Scanned:           {summary['scanned']} students\n"
            f"✓ Still on streak:   {summary['still_absent']}\n"
            f"✓ New alerts:        {summary['new_alerts']}\n"
            f"✓ Auto-resolved:     {summary['resolved']}\n"
        ))