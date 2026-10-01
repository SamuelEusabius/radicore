from django.db import models


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
    upi = models.CharField(
        max_length=30, blank=True,
        help_text="NEMIS UPI Number"
    )
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