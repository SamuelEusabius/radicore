import json
import urllib.request
from django.core.management.base import BaseCommand
from apps.locations.models import County, Constituency, Ward

class Command(BaseCommand):
    help = 'Downloads and seeds ALL 47 Kenyan Counties, 290 Constituencies, and 1,450 Wards'

    def handle(self, *args, **kwargs):
        self.stdout.write("Downloading location data...")
        
        # Verified public URL with full JSON dataset
        url = "https://raw.githubusercontent.com/kenyanlocations/kenya-locations-api/master/locations.json"
        
        # Backup URL if the first one fails
        backup_url = "https://raw.githubusercontent.com/tigawanna/kenya_wards_geojson_data/main/src/data/locations.json"

        data = None
        for attempt_url in [url, backup_url]:
            try:
                with urllib.request.urlopen(attempt_url) as response:
                    data = json.loads(response.read().decode())
                self.stdout.write(self.style.SUCCESS(f"Successfully downloaded from: {attempt_url}"))
                break
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed attempt: {e}"))
        
        if not data:
            self.stdout.write(self.style.ERROR("All download attempts failed. Please check your internet."))
            return

        self.stdout.write("Clearing old data...")
        Ward.objects.all().delete()
        Constituency.objects.all().delete()
        County.objects.all().delete()

        county_count = 0
        const_count = 0
        ward_count = 0

        self.stdout.write("Inserting data in UPPERCASE...")

        # Handle different JSON structures (dict vs list)
        county_list = data if isinstance(data, list) else [dict(name=k, **v) for k, v in data.items()]

        for county_data in county_list:
            county_name = county_data.get('name', county_data.get('county', '')).upper()
            county_code = str(county_data.get('code', county_name[:3])).zfill(3)

            county_obj, _ = County.objects.get_or_create(
                code=county_code,
                defaults={'name': county_name}
            )
            county_count += 1

            for const_data in county_data.get('constituencies', []):
                const_name = const_data.get('name', const_data.get('constituency', '')).upper()
                const_code = str(const_data.get('code', const_name[:5]))

                const_obj, _ = Constituency.objects.get_or_create(
                    code=const_code,
                    defaults={'name': const_name, 'county': county_obj}
                )
                const_count += 1

                for ward_data in const_data.get('wards', []):
                    ward_name = ward_data.get('name', ward_data.get('ward', '')).upper()
                    ward_code = str(ward_data.get('code', ward_name[:5]))

                    Ward.objects.get_or_create(
                        code=ward_code,
                        defaults={'name': ward_name, 'constituency': const_obj}
                    )
                    ward_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {county_count} Counties, {const_count} Constituencies, and {ward_count} Wards."
        ))