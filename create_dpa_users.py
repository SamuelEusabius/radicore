import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.schools.models import School

school = School.objects.get(slug="nairibischool")

for email, username, first, last in [
    ("dpa.admin@nairobi.school", "dpa_admin", "Deputy", "Admin"),
    ("dpa.academics@nairobi.school", "dpa_academics", "Deputy", "Academics"),
]:
    u, created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": username,
            "role": Role.DEPUTY_ADMIN if "admin@" in email else Role.DEPUTY_ACADEMICS,
            "school": school,
            "first_name": first,
            "last_name": last,
            "is_active": True,
        },
    )
    if created:
        u.set_password("TempPass123!")
        u.save()
        print(f"Created: {email} / TempPass123!  role={u.role}")
    else:
        print(f"Exists: {email} role={u.role}")