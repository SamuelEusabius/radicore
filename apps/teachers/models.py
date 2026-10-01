from django.db import models


class Teacher(models.Model):
    class EmploymentType(models.TextChoices):
        TSC       = 'tsc',       'TSC Employed'
        BOM       = 'bom',       'BOM Employed'
        INTERN    = 'intern',    'Intern'
        CONTRACT  = 'contract',  'Contract'

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, related_name='teachers')
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='teacher_profile')

    # Identification
    employee_number = models.CharField(max_length=30)
    tsc_number = models.CharField(max_length=30, blank=True, help_text="TSC Registration Number")
    id_number = models.CharField(max_length=20, blank=True, help_text="National ID")

    # Personal
    first_name = models.CharField(max_length=80, blank=True)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female')], blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='teachers/photos/', blank=True, null=True)

    # Role
    subject_specialty = models.CharField(max_length=200, blank=True)
    employment_type = models.CharField(max_length=10, choices=EmploymentType.choices, default=EmploymentType.TSC)
    is_class_teacher = models.BooleanField(default=False)

    # Current assignment
    current_class = models.ForeignKey('academics.ClassLevel', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='class_teachers')

    hire_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [('school', 'employee_number')]

    def __str__(self):
        return f"{self.employee_number} — {self.user.get_full_name() or self.user.email}"