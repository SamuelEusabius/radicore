from django.db import models

from apps.schools.managers import TenantManager

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
    objects = TenantManager()

    class Meta:
        unique_together = [('school', 'employee_number')]

    def __str__(self):
        return f"{self.employee_number} — {self.user.get_full_name() or self.user.email}"
    
    

# ==========================================================
# TEACHING OBSERVATIONS
# ==========================================================

class ObservationRating(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    GOOD      = 'good',      'Good'
    FAIR      = 'fair',      'Fair'
    NEEDS_IMPROVEMENT = 'needs_improvement', 'Needs Improvement'
    UNSATISFACTORY = 'unsatisfactory', 'Unsatisfactory'


class TeachingObservation(models.Model):
    """
    A formal classroom observation of a teacher.
    Conducted by DPA Academics or Principal.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='teaching_observations',
    )
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name='observations',
    )
    class_level = models.ForeignKey(
        'academics.ClassLevel', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='observations',
    )
    subject = models.ForeignKey(
        'academics.Subject', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='observations',
    )

    observed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='observations_made',
    )
    observed_on = models.DateField()
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    # Ratings per aspect (1-5 scale is common in Kenyan schools)
    rating_lesson_prep = models.PositiveIntegerField(
        null=True, blank=True, help_text="1-5",
    )
    rating_delivery = models.PositiveIntegerField(null=True, blank=True, help_text="1-5")
    rating_class_control = models.PositiveIntegerField(null=True, blank=True, help_text="1-5")
    rating_student_engagement = models.PositiveIntegerField(null=True, blank=True, help_text="1-5")
    rating_assessment = models.PositiveIntegerField(null=True, blank=True, help_text="1-5")
    overall_rating = models.CharField(
        max_length=25, choices=ObservationRating.choices, blank=True, default='',
    )

    strengths = models.TextField(blank=True, default='')
    areas_for_improvement = models.TextField(blank=True, default='')
    recommendations = models.TextField(blank=True, default='')

    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_done = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-observed_on']
        verbose_name = 'Teaching Observation'
        verbose_name_plural = 'Teaching Observations'
        indexes = [
            models.Index(fields=['school', 'observed_on']),
            models.Index(fields=['teacher', 'observed_on']),
        ]

    def __str__(self):
        return f"{self.teacher} — {self.observed_on}"

    @property
    def average_rating(self):
        ratings = [
            self.rating_lesson_prep,
            self.rating_delivery,
            self.rating_class_control,
            self.rating_student_engagement,
            self.rating_assessment,
        ]
        valid = [r for r in ratings if r is not None]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 1)