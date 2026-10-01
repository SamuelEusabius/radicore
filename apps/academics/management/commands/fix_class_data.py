"""
Data cleanup command for class name mismatches.

Run with --dry-run first to see what would change.
Then run without --dry-run to apply.

Usage:
    python manage.py fix_class_data --dry-run
    python manage.py fix_class_data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.academics.models import ClassLevel
from apps.students.models import Student


# Standard canonical class names
CANONICAL_CLASSES = [
    ('PP1', 'pp1'),
    ('PP2', 'pp2'),
    ('GRADE 1 EAST', 'g1e'),
    ('GRADE 1 WEST', 'g1w'),
    ('GRADE 2 EAST', 'g2e'),
    ('GRADE 2 WEST', 'g2w'),
    ('GRADE 3 EAST', 'g3e'),
    ('GRADE 3 WEST', 'g3w'),
    ('GRADE 4 EAST', 'g4e'),
    ('GRADE 4 WEST', 'g4w'),
    ('GRADE 5 EAST', 'g5e'),
    ('GRADE 5 WEST', 'g5w'),
    ('GRADE 6 EAST', 'g6e'),
    ('GRADE 6 WEST', 'g6w'),
    ('GRADE 7 EAST', 'g7e'),
    ('GRADE 7 WEST', 'g7w'),
    ('GRADE 8 EAST', 'g8e'),
    ('GRADE 8 WEST', 'g8w'),
    ('GRADE 9 EAST', 'g9e'),
    ('GRADE 9 WEST', 'g9w'),
]


def normalize(name):
    """Normalize a class name: uppercase, single-space, strip."""
    if not name:
        return ''
    return ' '.join(name.upper().split())


class Command(BaseCommand):
    help = 'Fix class name mismatches between ClassLevel and Student'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would change without applying'
        )
        parser.add_argument(
            '--school-id', type=int, default=None,
            help='Only process a specific school ID'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        school_id = options.get('school_id')

        self.stdout.write(self.style.WARNING(
            f"\n{'DRY RUN MODE' if dry_run else 'APPLYING CHANGES'}\n"
        ))

        # ---------- Phase 1: Fix ClassLevel ----------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Phase 1: ClassLevel cleanup ==='))

        qs = ClassLevel.objects.all()
        if school_id:
            qs = qs.filter(school_id=school_id)

        # Group by normalized name — detect duplicates
        from collections import defaultdict
        groups = defaultdict(list)
        for c in qs:
            groups[normalize(c.name)].append(c)

        for norm_name, items in groups.items():
            if len(items) > 1:
                self.stdout.write(self.style.ERROR(
                    f"  DUPLICATE: '{norm_name}' has {len(items)} rows: "
                    f"{[(i.id, i.name) for i in items]}"
                ))
                # Keep the FIRST one, delete the rest
                keep, *dupes = sorted(items, key=lambda x: x.id)
                self.stdout.write(self.style.WARNING(
                    f"    Would keep id={keep.id} ({keep.name}), "
                    f"delete {[d.id for d in dupes]}"
                ))
                if not dry_run:
                    ClassLevel.objects.filter(id__in=[d.id for d in dupes]).delete()
                    self.stdout.write(self.style.SUCCESS(f"    ✓ Deleted {len(dupes)} duplicates"))

            # Normalize the name
            item = items[0]
            norm = normalize(item.name)
            if item.name != norm:
                self.stdout.write(self.style.WARNING(
                    f"  RENAME: id={item.id} '{item.name}' → '{norm}'"
                ))
                if not dry_run:
                    item.name = norm
                    item.save(update_fields=['name'])

        # ---------- Phase 2: Add missing classes ----------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Phase 2: Add missing classes ==='))

        existing = set(ClassLevel.objects.values_list('name', flat=True))

        # Group by school
        schools = set(Student.objects.values_list('school_id', flat=True))
        if school_id:
            schools = {school_id}

        for sid in schools:
            for canonical_name, code in CANONICAL_CLASSES:
                if canonical_name not in existing:
                    self.stdout.write(self.style.WARNING(
                        f"  ADD: school={sid} class='{canonical_name}'"
                    ))
                    if not dry_run:
                        # Find order from previous class
                        order_map = {name: i for i, (name, _) in enumerate(CANONICAL_CLASSES)}
                        ClassLevel.objects.create(
                            school_id=sid,
                            name=canonical_name,
                            order=order_map[canonical_name],
                        )
                        self.stdout.write(self.style.SUCCESS(f"    ✓ Created"))

        # ---------- Phase 3: Match students to classes ----------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Phase 3: Student class matching ==='))

        qs = Student.objects.all()
        if school_id:
            qs = qs.filter(school_id=school_id)

        unmatched = []
        for s in qs:
            norm = normalize(s.class_level)
            if not norm:
                continue
            if norm != s.class_level:
                self.stdout.write(self.style.WARNING(
                    f"  NORMALIZE: student {s.id} '{s.class_level}' → '{norm}'"
                ))
                if not dry_run:
                    s.class_level = norm
                    s.save(update_fields=['class_level'])

            # Check if this class exists in ClassLevel
            if not ClassLevel.objects.filter(school=s.school, name=norm).exists():
                unmatched.append((s.id, s.full_name, norm, s.school_id))

        if unmatched:
            self.stdout.write(self.style.ERROR('\n  UNMATCHED students (need manual fix):'))
            for sid, name, cls, school_id in unmatched:
                self.stdout.write(f"    student id={sid} ({name}) → '{cls}' (school {school_id})")
        else:
            self.stdout.write(self.style.SUCCESS('\n  ✓ All students matched to existing classes'))

        # ---------- Summary ----------
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Summary ==='))
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\nThis was a DRY RUN. Nothing was changed.\n'
                'To apply: python manage.py fix_class_data\n'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '\n✓ All changes applied.\n'
            ))