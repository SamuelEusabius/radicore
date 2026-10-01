from django.db import models


class NonTeachingStaff(models.Model):
    class Role(models.TextChoices):
        SECURITY      = 'security',      'Security / Guard'
        COOK          = 'cook',          'Cook'
        DRIVER        = 'driver',        'Driver'
        CLEANER       = 'cleaner',       'Cleaner'
        NURSE         = 'nurse',         'Nurse'
        GROUNDSKEEPER = 'groundskeeper', 'Groundskeeper'
        SECRETARY     = 'secretary',     'Secretary / Receptionist'
        LIBRARIAN     = 'librarian',     'Librarian'
        OTHER         = 'other',         'Other'

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='non_teaching_staff')

    full_name = models.CharField(max_length=100)
    id_number = models.CharField(max_length=20, help_text="National ID")
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to='staff/photos/', blank=True, null=True)

    date_of_birth = models.DateField(null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['role', 'full_name']

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"