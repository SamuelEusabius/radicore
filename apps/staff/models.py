from django.db import models
from django.conf import settings


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
    
    # ==========================================================
# LEAVE REQUESTS
# ==========================================================

class LeaveType(models.TextChoices):
    ANNUAL       = 'annual',       'Annual Leave'
    SICK         = 'sick',         'Sick Leave'
    MATERNITY    = 'maternity',    'Maternity Leave'
    PATERNITY    = 'paternity',    'Paternity Leave'
    COMPASSIONATE = 'compassionate', 'Compassionate Leave'
    STUDY        = 'study',        'Study Leave'
    UNPAID       = 'unpaid',       'Unpaid Leave'
    OTHER        = 'other',        'Other'


class LeaveStatus(models.TextChoices):
    PENDING   = 'pending',   'Pending'
    APPROVED  = 'approved',  'Approved'
    REJECTED  = 'rejected',  'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class LeaveRequest(models.Model):
    """A staff member's request for leave."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='leave_requests'
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.PositiveIntegerField(default=1)
    reason = models.TextField(blank=True, default='')

    status = models.CharField(
        max_length=20, choices=LeaveStatus.choices, default=LeaveStatus.PENDING
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    # Approval chain — Deputy Admin first, then Principal
    dpa_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leave_dpa_approved',
    )
    dpa_approved_at = models.DateTimeField(null=True, blank=True)
    dpa_comment = models.TextField(blank=True, default='')

    principal_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leave_principal_approved',
    )
    principal_approved_at = models.DateTimeField(null=True, blank=True)
    principal_comment = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'start_date']),
            models.Index(fields=['staff', 'status']),
        ]

    def __str__(self):
        return f"{self.staff} — {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"

    @property
    def is_pending_dpa(self):
        return self.status == LeaveStatus.PENDING and self.dpa_approved_at is None

    @property
    def is_pending_principal(self):
        return (
            self.status == LeaveStatus.PENDING
            and self.dpa_approved_at is not None
            and self.principal_approved_at is None
        )


# ==========================================================
# DUTY ROSTER
# ==========================================================

class DutyType(models.TextChoices):
    MORNING_PREP    = 'morning_prep',    'Morning Prep'
    BREAK_DUTY      = 'break_duty',      'Break Duty'
    LUNCH_DUTY      = 'lunch_duty',      'Lunch Duty'
    EVENING_PREP    = 'evening_prep',    'Evening Prep'
    WEEKEND_DUTY    = 'weekend_duty',    'Weekend Duty'
    NIGHT_DUTY      = 'night_duty',      'Night Duty'
    ASSEMBLY        = 'assembly',        'Assembly'
    GATE_DUTY       = 'gate_duty',       'Gate Duty'
    OTHER           = 'other',           'Other'


class DutyRoster(models.Model):
    """A scheduled duty assignment for a staff member."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='duty_rosters'
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='duty_rosters',
    )
    duty_type = models.CharField(max_length=20, choices=DutyType.choices)
    duty_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='duties_assigned',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-duty_date', 'start_time']
        indexes = [
            models.Index(fields=['school', 'duty_date']),
            models.Index(fields=['staff', 'duty_date']),
        ]
        unique_together = [('school', 'staff', 'duty_date', 'duty_type')]

    def __str__(self):
        return f"{self.staff} — {self.get_duty_type_display()} on {self.duty_date}"


# ==========================================================
# STAFF ATTENDANCE
# ==========================================================

class StaffAttendanceStatus(models.TextChoices):
    PRESENT   = 'present',   'Present'
    ABSENT    = 'absent',    'Absent'
    LATE      = 'late',      'Late'
    ON_LEAVE  = 'on_leave',  'On Leave'
    HALF_DAY  = 'half_day',  'Half Day'


class StaffAttendance(models.Model):
    """Daily attendance record for a staff member."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='staff_attendance'
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_attendance_records',
    )
    date = models.DateField()
    status = models.CharField(
        max_length=20, choices=StaffAttendanceStatus.choices, default=StaffAttendanceStatus.PRESENT
    )
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default='')

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='staff_attendance_recorded',
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'staff']
        indexes = [
            models.Index(fields=['school', 'date']),
            models.Index(fields=['staff', 'date']),
        ]
        unique_together = [('school', 'staff', 'date')]
        verbose_name = 'Staff Attendance'
        verbose_name_plural = 'Staff Attendance'

    def __str__(self):
        return f"{self.staff} — {self.get_status_display()} on {self.date}"