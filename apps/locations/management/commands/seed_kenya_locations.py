"""
Seed Kenyan counties, constituencies, and wards from the
alvinchesaro/Kenya-Counties-SubCounties-and-Wards JSON file.

Structure expected:
{
    "Mombasa": {
        "Changamwe": ["Port Reitz", "Kipevu", ...],
        ...
    },
    ...
}

Usage:
    python manage.py seed_kenya_locations
    python manage.py seed_kenya_locations --flush
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.locations.models import County, Constituency, Ward


def _slug_code(prefix: str, index: int, name: str) -> str:
    """Generate a stable code like MSA-001, CNST-042, WARD-1378."""
    return f"{prefix}-{index:03d}"


class Command(BaseCommand):
    help = 'Seed Kenyan counties, constituencies, and wards from JSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', type=str, default=None,
            help='Path to JSON file (default: apps/locations/data/kenya_locations.json)'
        )
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete all existing Counties/Constituencies/Wards before seeding'
        )

    def handle(self, *args, **options):
        json_path = options['file']
        if not json_path:
            json_path = os.path.join(
                settings.BASE_DIR, 'apps', 'locations', 'data',
                'kenya_locations.json'
            )

        if not os.path.exists(json_path):
            raise CommandError(
                f"JSON file not found: {json_path}\n"
                f"Download from: "
                f"https://raw.githubusercontent.com/alvinchesaro/"
                f"Kenya-Counties-SubCounties-and-Wards/main/"
                f"Kenya-Counties-SubCounties-and-Wards.json"
            )

        self.stdout.write(f"Loading: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise CommandError(
                "Expected a dict at top level (county → constituency → wards)."
            )

        if options['flush']:
            self.stdout.write(self.style.WARNING("Flushing existing locations..."))
            Ward.objects.all().delete()
            Constituency.objects.all().delete()
            County.objects.all().delete()

        stats = {'counties': 0, 'constituencies': 0, 'wards': 0}

        with transaction.atomic():
            for c_idx, (county_name, constituencies) in enumerate(data.items(), start=1):
                # County code: use name-based prefix + sequence
                c_code = _slug_code('CTY', c_idx, county_name)
                county, _ = County.objects.update_or_create(
                    name=county_name,
                    defaults={'code': c_code},
                )
                stats['counties'] += 1

                if not isinstance(constituencies, dict):
                    continue

                for cons_idx, (cons_name, wards) in enumerate(
                    constituencies.items(), start=1
                ):
                    cons_code = f"{c_code}-C{cons_idx:03d}"
                    cons, _ = Constituency.objects.update_or_create(
                        county=county,
                        name=cons_name,
                        defaults={'code': cons_code},
                    )
                    stats['constituencies'] += 1

                    if not isinstance(wards, list):
                        continue

                    for w_idx, ward_name in enumerate(wards, start=1):
                        if not isinstance(ward_name, str) or not ward_name.strip():
                            continue
                        ward_code = f"{cons_code}-W{w_idx:03d}"
                        Ward.objects.update_or_create(
                            constituency=cons,
                            name=ward_name.strip(),
                            defaults={'code': ward_code},
                        )
                        stats['wards'] += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Counties: {stats['counties']}, "
            f"Constituencies: {stats['constituencies']}, "
            f"Wards: {stats['wards']}"
        ))