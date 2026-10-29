from django.db import models
from apps.schools.managers import TenantManager
from django.conf import settings


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE   = 'M', 'Male'
        FEMALE = 'F', 'Female'

    class CBCLevel(models.TextChoices):
        PP1  = 'pp1',  'PP1'
        PP2  = 'pp2',  'PP2'
        G1   = 'g1',   'Grade 1'
        G2   = 'g2',   'Grade 2'
        G3   = 'g3',   'Grade 3'
        G4   = 'g4',   'Grade 4'
        G5   = 'g5',   'Grade 5'
        G6   = 'g6',   'Grade 6'
        G7   = 'g7',   'Grade 7 (JSS 1)'
        G8   = 'g8',   'Grade 8 (JSS 2)'
        G9   = 'g9',   'Grade 9 (JSS 3)'
        G10  = 'g10',  'Grade 10 (Senior 1)'
        G11  = 'g11',  'Grade 11 (Senior 2)'
        G12  = 'g12',  'Grade 12 (Senior 3)'

    # ============ RELATIONSHIPS ============
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='students'
    )
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='student_profile'
    )
    
        # ============ CLEARANCE ============
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)
    clearance_reason = models.CharField(max_length=200, blank=True, default='')
    leaving_certificate_notes = models.TextField(blank=True, default='')
        # ============ CLEARANCE ============
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)
    clearance_reason = models.CharField(max_length=200, blank=True, default='')
    leaving_certificate_notes = models.TextField(blank=True, default='')
    leaving_certificate_content = models.TextField(blank=True, default='', help_text="Rich HTML body content")
    # ============ IDENTIFICATION ============
    upi = models.CharField(max_length=50, blank=True, null=True)
    parent_id_number = models.CharField(max_length=20, blank=True, null=True)
    previous_school_marks = models.CharField(max_length=50, blank=True, null=True)
    previous_school_mean_grade = models.CharField(max_length=10, blank=True, null=True)
    admission_number = models.CharField(max_length=30)
    birth_certificate_number = models.CharField(max_length=30, blank=True)

    # ============ PERSONAL ============
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='students/photos/', blank=True, null=True)

    # ============ ACADEMIC ============
    cbc_level = models.CharField(
        max_length=5, choices=CBCLevel.choices, blank=True
    )
    class_level = models.CharField(
        max_length=30, blank=True,
        help_text="e.g. Grade 5 East"
    )
    admission_date = models.DateField(null=True, blank=True)

    # ============ GUARDIAN (fallback if not linked to a Parent) ============
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_relationship = models.CharField(max_length=30, blank=True)

    # ============ SPECIAL NEEDS ============
    has_special_needs = models.BooleanField(default=False)
    special_needs_notes = models.TextField(blank=True)

    # ============ STATUS ============
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = TenantManager()
    
        # ============ LOCATION (Kenyan cascade) ============
    county_fk = models.ForeignKey(
        'locations.County', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students',
        db_column='county_fk_id'
    )
    constituency_fk = models.ForeignKey(
        'locations.Constituency', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students',
        db_column='constituency_fk_id'
    )
    ward_fk = models.ForeignKey(
        'locations.Ward', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students',
        db_column='ward_fk_id'
    )
    sub_county = models.CharField(max_length=50, blank=True, default='')
    location = models.CharField(max_length=100, blank=True, default='')
    village = models.CharField(max_length=100, blank=True, default='')

    # ============ DISABILITY & MEDICAL ============
    has_disability = models.BooleanField(default=False)
    disability_details = models.TextField(blank=True, default='')
    has_medical_condition = models.BooleanField(default=False)
    medical_condition_details = models.TextField(blank=True, default='')
    requires_medication = models.BooleanField(default=False)
    medication_notes = models.TextField(blank=True, default='')

    # ============ BOARDING ============
    is_boarding = models.BooleanField(
        default=False,
        help_text="Whether this student is a boarding student"
    )
    class Meta:
        ordering = ['first_name', 'last_name']
        unique_together = [('school', 'admission_number')]
        indexes = [
            models.Index(fields=['school', 'is_active']),
            models.Index(fields=['school', 'class_level']),
            models.Index(fields=['admission_number']),
        ]

    def __str__(self):
        return f"{self.admission_number} — {self.first_name} {self.last_name}"

    # ============ PROPERTIES ============
    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def initials(self):
        first = (self.first_name or '')[:1]
        last = (self.last_name or '')[:1]
        return f"{first}{last}".upper()

    # ============ ADMISSION NUMBER AUTO-GENERATION ============
    @staticmethod
    def generate_admission_number(school, gender, start_from=1):
        """
        Generate the next admission number in format:
        00001B for boys, 00001G for girls.

        Logic:
        - Scans all existing admission numbers for this school
        - Finds the highest number used
        - Adds 1 (or starts at `start_from` if fresh)
        - Suffixes with B (boy) or G (girl)

        If the last admission number was for the OTHER gender,
        we keep incrementing (so 00001B → 00002G → 00003B, etc.)
        """
        # Get all existing admission numbers for this school
        existing = Student.objects.filter(school=school).values_list(
            'admission_number', flat=True
        )

        max_num = start_from - 1

        for adm in existing:
            if not adm:
                continue
            # Extract leading digits (stop at first non-digit)
            digits = ''
            for ch in adm:
                if ch.isdigit():
                    digits += ch
                else:
                    break

            if digits:
                try:
                    n = int(digits)
                    if n > max_num:
                        max_num = n
                except ValueError:
                    continue

        next_num = max_num + 1
        suffix = 'B' if gender == 'M' else 'G'
        return f"{next_num:05d}{suffix}"


class CoCurricularActivity(models.Model):
    class Category(models.TextChoices):
        SPORTS     = 'sports',     'Sports'
        CLUBS      = 'clubs',      'Clubs & Societies'
        ARTS       = 'arts',       'Creative Arts'
        MUSIC      = 'music',      'Music & Drama'
        LEADERSHIP = 'leadership', 'Leadership'
        OTHER      = 'other',      'Other'

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='activities'
    )
    name = models.CharField(max_length=100, help_text="e.g. Football, Drama Club")
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.OTHER
    )
    role = models.CharField(
        max_length=50, blank=True,
        help_text="e.g. Team Captain, Member"
    )
    joined_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-joined_date', 'name']

    def __str__(self):
        return f"{self.name} — {self.student.full_name}"
    
    

# ==========================================================
# STUDENT MOVEMENT LOG (in/out during school hours)
# ==========================================================

class StudentMovementDirection(models.TextChoices):
    OUT = 'out', 'Out'
    IN = 'in', 'In'


class StudentMovementReason(models.TextChoices):
    SICK_BAY         = 'sick_bay',         'Sick Bay'
    MEDICAL          = 'medical',          'Medical Appointment'
    FAMILY_EMERGENCY = 'family_emergency', 'Family Emergency'
    EARLY_DEPARTURE  = 'early_departure',  'Early Departure'
    ERRAND           = 'errand',           'School Errand'
    SPORTS           = 'sports',           'Sports / Competition'
    SUSPENSION       = 'suspension',       'Suspension'
    OTHER            = 'other',            'Other'


class StudentMovement(models.Model):
    """A student leaving or returning to school during the school day."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='student_movements',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='movements',
    )
    direction = models.CharField(max_length=5, choices=StudentMovementDirection.choices)
    movement_date = models.DateField()
    movement_time = models.TimeField(auto_now_add=True)
    reason = models.CharField(max_length=25, choices=StudentMovementReason.choices)
    reason_notes = models.TextField(blank=True, default='')

    # Who authorized (deputy, nurse, principal)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='student_movements_authorized',
    )
    # Who physically released/received the student (security, teacher on duty)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='student_movements_released',
    )

    # Guardian notification
    guardian_notified = models.BooleanField(default=False)
    guardian_notified_at = models.DateTimeField(null=True, blank=True)

    # For OUT entries — was the student expected back?
    expected_return_time = models.TimeField(null=True, blank=True)
    actual_return_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-movement_date', '-movement_time']
        indexes = [
            models.Index(fields=['school', 'movement_date']),
            models.Index(fields=['student', 'movement_date']),
            models.Index(fields=['school', 'direction']),
        ]
        verbose_name = 'Student Movement'
        verbose_name_plural = 'Student Movements'

    def __str__(self):
        return f"{self.student} — {self.get_direction_display()} on {self.movement_date}"


# ==========================================================
# STUDENT ADMINISTRATIVE CASES (non-discipline)
# ==========================================================

class AdminCaseType(models.TextChoices):
    MEDICAL       = 'medical',        'Medical'
    FAMILY        = 'family',         'Family Matter'
    FINANCIAL     = 'financial',      'Financial Hardship'
    TRANSPORT     = 'transport',      'Transport Issue'
    UNIFORM       = 'uniform',        'Uniform / Supplies'
    ACCOMMODATION = 'accommodation',  'Accommodation'
    WELFARE       = 'welfare',        'General Welfare'
    TRANSFER      = 'transfer',       'Transfer Request'
    OTHER         = 'other',          'Other'


class AdminCaseStatus(models.TextChoices):
    OPEN      = 'open',      'Open'
    IN_REVIEW = 'in_review', 'In Review'
    RESOLVED  = 'resolved',  'Resolved'
    REFERRED  = 'referred',  'Referred to Principal'
    CLOSED    = 'closed',    'Closed'


class AdminCasePriority(models.TextChoices):
    LOW    = 'low',    'Low'
    NORMAL = 'normal', 'Normal'
    HIGH   = 'high',   'High'
    URGENT = 'urgent', 'Urgent'


class StudentAdminCase(models.Model):
    """An administrative case about a student — not discipline."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='student_admin_cases',
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='admin_cases',
    )

    case_type = models.CharField(max_length=20, choices=AdminCaseType.choices)
    priority = models.CharField(
        max_length=10, choices=AdminCasePriority.choices, default=AdminCasePriority.NORMAL,
    )
    title = models.CharField(max_length=200)
    description = models.TextField()

    status = models.CharField(
        max_length=15, choices=AdminCaseStatus.choices, default=AdminCaseStatus.OPEN,
    )

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admin_cases_opened',
    )
    opened_at = models.DateTimeField(auto_now_add=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admin_cases_assigned',
    )

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admin_cases_resolved',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, default='')

    guardian_informed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'case_type']),
            models.Index(fields=['student', 'status']),
        ]
        verbose_name = 'Student Admin Case'
        verbose_name_plural = 'Student Admin Cases'

    def __str__(self):
        return f"{self.student} — {self.title} ({self.get_status_display()})"
    
        # For physical document tracking
    previous_school_marks = models.CharField(max_length=50, blank=True, null=True)
    previous_school_mean_grade = models.CharField(max_length=10, blank=True, null=True)
    parent_id_number = models.CharField(max_length=20, blank=True, null=True)