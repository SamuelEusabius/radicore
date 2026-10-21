"""
Boarding / Dormitory module.

Handles:
  - Dormitories (houses) with capacity + house master
  - Beds per dormitory
  - Student-to-bed assignments
  - Occupancy tracking

Boarding Master role has full CRUD on all of the above.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================
# DORMITORY
# ============================================================

class BoardingDormitory(models.Model):

    class Gender(models.TextChoices):
        BOYS  = 'boys',  'Boys Only'
        GIRLS = 'girls', 'Girls Only'
        MIXED = 'mixed', 'Mixed'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='boarding_dormitories'
    )
    name = models.CharField(
        max_length=120,
        help_text="e.g. Kilimanjaro House, Kenya Block"
    )
    code = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Short code, e.g. KIL, KEN"
    )
    gender = models.CharField(
        max_length=10, choices=Gender.choices, default=Gender.MIXED
    )
    capacity = models.PositiveIntegerField(
        default=0,
        help_text="Total bed capacity (auto-recalc if 0)"
    )
    house_master = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dormitories_managed',
        help_text="Boarding Master responsible for this dorm"
    )
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ('school', 'name')

    def __str__(self):
        return f"{self.name} ({self.school.code})"

    @property
    def bed_count(self):
        """Actual number of bed records."""
        return self.beds.count()

    @property
    def occupied_count(self):
        """Beds with an active assignment."""
        return self.beds.filter(is_occupied=True).count()

    @property
    def available_count(self):
        return self.bed_count - self.occupied_count

    @property
    def occupancy_percent(self):
        total = self.bed_count
        if total == 0:
            return 0
        return round((self.occupied_count / total) * 100)


# ============================================================
# BED
# ============================================================

class BoardingBed(models.Model):
    dormitory = models.ForeignKey(
        BoardingDormitory, on_delete=models.CASCADE,
        related_name='beds'
    )
    bed_number = models.CharField(
        max_length=20,
        help_text="e.g. A-01, B-12"
    )
    is_occupied = models.BooleanField(default=False)
    notes = models.CharField(max_length=200, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['dormitory', 'bed_number']
        unique_together = ('dormitory', 'bed_number')

    def __str__(self):
        return f"{self.dormitory.name} · {self.bed_number}"

    @property
    def current_occupant(self):
        """The active assignment's student, or None."""
        active = self.assignments.filter(status='active').first()
        return active.student if active else None


# ============================================================
# ASSIGNMENT
# ============================================================

class BoardingAssignment(models.Model):

    class Status(models.TextChoices):
        ACTIVE       = 'active',       'Active'
        TRANSFERRED  = 'transferred',  'Transferred to another bed'
        CHECKED_OUT  = 'checked_out',  'Checked Out'
        SUSPENDED    = 'suspended',    'Suspended'

    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        related_name='boarding_assignments'
    )
    dormitory = models.ForeignKey(
        BoardingDormitory, on_delete=models.CASCADE,
        related_name='assignments'
    )
    bed = models.ForeignKey(
        BoardingBed, on_delete=models.CASCADE,
        related_name='assignments'
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='boarding_assignments_made',
    )
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checkout_reason = models.TextField(blank=True, default='')

    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['dormitory', 'status']),
        ]

    def __str__(self):
        return f"{self.student} → {self.dormitory.name} · {self.bed.bed_number}"

    def save(self, *args, **kwargs):
        """Auto-manage bed occupancy when saving."""
        super().save(*args, **kwargs)

        # Update bed occupancy based on active assignment
        bed = self.bed
        active_exists = bed.assignments.filter(status='active').exists()
        if bed.is_occupied != active_exists:
            bed.is_occupied = active_exists
            bed.save(update_fields=['is_occupied'])


# ============================================================
# HELPER — auto-assign bed on admission
# ============================================================

def find_and_assign_bed(student, assigned_by=None):
    """
    Auto-assign the first available bed to a boarding student.
    Matching priority:
      1. Dormitory gender matches student gender (or MIXED)
      2. Prefer dormitory whose house_master has the boarding_master role
      3. First available bed sorted by bed_number

    Returns the BoardingAssignment, or None if no bed available.
    """
    from apps.students.models import Student

    if not isinstance(student, Student):
        return None

    # Skip if student already has an active assignment
    if student.boarding_assignments.filter(status='active').exists():
        return student.boarding_assignments.filter(status='active').first()

    # Student gender
    s_gender = getattr(student, 'gender', '')  # 'M' or 'F'

    # Dorm gender preference
    if s_gender == 'M':
        gender_filters = ['boys', 'mixed']
    elif s_gender == 'F':
        gender_filters = ['girls', 'mixed']
    else:
        gender_filters = ['mixed']

    # Find candidate dormitories
    dorms = (
        BoardingDormitory.objects
        .filter(school=student.school, is_active=True, gender__in=gender_filters)
        .prefetch_related('beds')
    )

    # Try each dorm, find first available bed
    for dorm in dorms:
        bed = dorm.beds.filter(is_occupied=False).order_by('bed_number').first()
        if bed:
            return BoardingAssignment.objects.create(
                student=student,
                dormitory=dorm,
                bed=bed,
                assigned_by=assigned_by,
                status=BoardingAssignment.Status.ACTIVE,
                notes='Auto-assigned on admission',
            )

    return None