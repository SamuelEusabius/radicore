"""
Security / Chief Security Officer (CSO) module.

Owns the master record of:
  - Visitors arriving at the school gate
  - Gate passes (standard + official)
  - Security incidents
  - Lost & found items
  - Guard shift roster

The Secretary module reads Visitor and GatePass to coordinate
admin-received official visits and to log out official visitors
after they meet with administration members.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================
# VISITOR — master record created by CSO at the gate
# ============================================================

class Visitor(models.Model):

    class IDType(models.TextChoices):
        NATIONAL_ID = 'national_id', 'National ID'
        PASSPORT    = 'passport',    'Passport'
        DRIVER      = 'driver',      "Driver's Licence"
        STAFF_ID    = 'staff_id',    'Staff ID'
        OTHER       = 'other',       'Other'

    class Purpose(models.TextChoices):
        MEETING       = 'meeting',       'Meeting with Staff'
        PARENT_VISIT  = 'parent_visit',  'Parent Visiting Student'
        DELIVERY      = 'delivery',      'Delivery / Supplier'
        OFFICIAL      = 'official',      'Government / Official Visit'
        MAINTENANCE   = 'maintenance',   'Maintenance / Contractor'
        INTERVIEW     = 'interview',     'Interview'
        OTHER         = 'other',         'Other'

    class VisitType(models.TextChoices):
        STANDARD = 'standard', 'Standard Visitor'
        OFFICIAL = 'official', 'Official (Administration) Visitor'

    class Status(models.TextChoices):
        REGISTERED  = 'registered',  'Registered at Gate'
        IN_MEETING  = 'in_meeting',  'With Host'
        SIGNED_OUT  = 'signed_out',  'Admin Signed Out'
        EXITED      = 'exited',      'Exited School'
        CANCELLED   = 'cancelled',   'Cancelled'

    # ---------- Relationships ----------
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='visitors'
    )

    # ---------- Visitor identity ----------
    full_name    = models.CharField(max_length=120)
    phone        = models.CharField(max_length=20, blank=True, default='')
    id_type      = models.CharField(
        max_length=20, choices=IDType.choices, default=IDType.NATIONAL_ID
    )
    id_number    = models.CharField(max_length=40, blank=True, default='')
    organisation = models.CharField(max_length=120, blank=True, default='')

    vehicle_plate = models.CharField(max_length=20, blank=True, default='')
    badge_number  = models.CharField(max_length=20, blank=True, default='')

    # ---------- Visit details ----------
    purpose       = models.CharField(
        max_length=20, choices=Purpose.choices, default=Purpose.MEETING
    )
    purpose_note  = models.TextField(blank=True, default='')

    visit_type    = models.CharField(
        max_length=10, choices=VisitType.choices, default=VisitType.STANDARD
    )

    # Who are they coming to see?
    host_user   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visitors_hosting',
        help_text="Staff member being visited"
    )
    host_name   = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Free text if host isn't a system user"
    )
    host_role   = models.CharField(
        max_length=32, blank=True, default='',
        help_text="Principal / DOS / Accountant / etc."
    )

    # ---------- Lifecycle timestamps ----------
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='visitors_registered',
        help_text="CSO who registered the visitor"
    )
    time_in = models.DateTimeField(default=timezone.now)

    # For OFFICIAL visitors — Secretary issues the official pass
    official_pass_issued_at = models.DateTimeField(null=True, blank=True)
    official_pass_issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='official_passes_issued',
        help_text="Secretary who issued the official pass"
    )

    # ---------- Admin signature (for OFFICIAL visitors) ----------
    admin_signed_at   = models.DateTimeField(null=True, blank=True)
    admin_signed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visitors_signed',
        help_text="Admin member who received the visitor"
    )
    admin_signed_name = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Signature name (fallback if not a system user)"
    )
    admin_signature_notes = models.TextField(blank=True, default='')

    admin_confirmed_by_secretary = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admin_signatures_confirmed',
        help_text="Secretary who confirmed the admin signature"
    )
    admin_confirmed_at = models.DateTimeField(null=True, blank=True)

    # ---------- Exit ----------
    time_out = models.DateTimeField(null=True, blank=True)
    logged_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='visitors_logged_out',
        help_text="CSO (standard) or Secretary (official)"
    )

    # ---------- Status ----------
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REGISTERED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-time_in']
        indexes = [
            models.Index(fields=['school', '-time_in']),
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'visit_type']),
        ]

    def __str__(self):
        return f"{self.full_name} @ {self.school.code} ({self.time_in:%d %b %H:%M})"

    # ---------- Helpers ----------
    @property
    def is_on_premises(self):
        return self.status in (
            self.Status.REGISTERED,
            self.Status.IN_MEETING,
            self.Status.SIGNED_OUT,
        )

    @property
    def is_official(self):
        return self.visit_type == self.VisitType.OFFICIAL

    @property
    def is_standard(self):
        return self.visit_type == self.VisitType.STANDARD

    @property
    def duration_minutes(self):
        end = self.time_out or timezone.now()
        return int((end - self.time_in).total_seconds() // 60)

    @property
    def host_display(self):
        if self.host_user:
            return self.host_user.get_full_name() or self.host_user.email
        return self.host_name or '—'


# ============================================================
# GATE PASS — issued at gate (standard) or by Secretary (official)
# ============================================================

class GatePass(models.Model):

    class PassType(models.TextChoices):
        STANDARD = 'standard', 'Standard Gate Pass'
        OFFICIAL = 'official', 'Official Visitor Pass'

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        ACTIVE    = 'active',    'Active'
        SIGNED    = 'signed',    'Signed by Admin'
        USED      = 'used',      'Used / Visitor Exited'
        EXPIRED   = 'expired',   'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    # ---------- Relationships ----------
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='gate_passes'
    )
    visitor = models.OneToOneField(
        Visitor, on_delete=models.CASCADE, related_name='gate_pass',
        null=True, blank=True,
    )

    # ---------- Pass identity ----------
    pass_number = models.CharField(max_length=30, unique=True, db_index=True)
    pass_type   = models.CharField(
        max_length=10, choices=PassType.choices, default=PassType.STANDARD
    )

    # ---------- Purpose / destination ----------
    destination = models.CharField(
        max_length=200, blank=True, default='',
        help_text="e.g. Principal's Office, Accounts Office, Class 5 East"
    )

    # ---------- Validity ----------
    valid_from  = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    # ---------- Issued by ----------
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='gate_passes_issued',
    )
    issued_at = models.DateTimeField(default=timezone.now)

    # ---------- Signed by admin (official only) ----------
    signed_by_name = models.CharField(max_length=120, blank=True, default='')
    signed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='gate_passes_signed',
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_image = models.ImageField(
        upload_to='gate_pass_signatures/', blank=True, null=True
    )

    # ---------- Lifecycle ----------
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['school', '-issued_at']),
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.pass_number} — {self.get_pass_type_display()}"

    def save(self, *args, **kwargs):
        if not self.pass_number:
            prefix = 'GP' if self.pass_type == self.PassType.STANDARD else 'OP'
            last = GatePass.objects.filter(
                school=self.school, pass_type=self.pass_type
            ).order_by('-id').first()
            seq = (int(last.id) + 1) if last else 1
            self.pass_number = f"{prefix}-{self.school.code}-{seq:05d}"
        super().save(*args, **kwargs)


# ============================================================
# INCIDENT
# ============================================================

class Incident(models.Model):

    class Severity(models.TextChoices):
        LOW      = 'low',      'Low'
        MEDIUM   = 'medium',   'Medium'
        HIGH     = 'high',     'High'
        CRITICAL = 'critical', 'Critical'

    class Category(models.TextChoices):
        THEFT      = 'theft',      'Theft'
        FIGHT      = 'fight',      'Fight / Assault'
        MEDICAL    = 'medical',    'Medical Emergency'
        FIRE       = 'fire',       'Fire / Fire Drill'
        TRESPASS   = 'trespass',   'Trespassing'
        VANDALISM  = 'vandalism',  'Vandalism'
        BULLYING   = 'bullying',   'Bullying'
        SUBSTANCE  = 'substance',  'Substance Abuse'
        OTHER      = 'other',      'Other'

    class Status(models.TextChoices):
        OPEN          = 'open',          'Open'
        INVESTIGATING = 'investigating', 'Investigating'
        RESOLVED      = 'resolved',      'Resolved'
        ESCALATED     = 'escalated',     'Escalated'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='incidents'
    )

    reference = models.CharField(max_length=30, unique=True, db_index=True)
    title     = models.CharField(max_length=200)
    category  = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    severity  = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    status    = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    location    = models.CharField(max_length=200, blank=True, default='')
    occurred_at = models.DateTimeField(default=timezone.now)
    description = models.TextField()
    action_taken = models.TextField(blank=True, default='')
    resolution   = models.TextField(blank=True, default='')

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='incidents_reported',
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_handled',
    )

    involved_student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='security_incidents',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['school', '-occurred_at']),
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.reference} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            last = Incident.objects.filter(school=self.school).order_by('-id').first()
            seq = (int(last.id) + 1) if last else 1
            self.reference = f"INC-{self.school.code}-{seq:04d}"
        super().save(*args, **kwargs)


# ============================================================
# LOST & FOUND
# ============================================================

class LostItem(models.Model):

    class ItemStatus(models.TextChoices):
        HELD     = 'held',     'Held at Security'
        CLAIMED  = 'claimed',  'Claimed'
        DONATED  = 'donated',  'Donated'
        DISPOSED = 'disposed', 'Disposed'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='lost_items'
    )
    name           = models.CharField(max_length=120)
    description    = models.TextField(blank=True, default='')
    found_at       = models.DateTimeField(default=timezone.now)
    found_location = models.CharField(max_length=200, blank=True, default='')

    status = models.CharField(
        max_length=10, choices=ItemStatus.choices, default=ItemStatus.HELD
    )

    claimed_by_name  = models.CharField(max_length=120, blank=True, default='')
    claimed_by_phone = models.CharField(max_length=20, blank=True, default='')
    claimed_at       = models.DateTimeField(null=True, blank=True)

    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='lost_items_logged',
    )

    class Meta:
        ordering = ['-found_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


# ============================================================
# SECURITY SHIFT — guard roster
# ============================================================

class SecurityShift(models.Model):

    class ShiftType(models.TextChoices):
        MORNING   = 'morning',   'Morning (06:00–14:00)'
        AFTERNOON = 'afternoon', 'Afternoon (14:00–22:00)'
        NIGHT     = 'night',     'Night (22:00–06:00)'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='security_shifts'
    )
    guard = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='security_shifts',
    )
    shift_date = models.DateField()
    shift_type = models.CharField(max_length=10, choices=ShiftType.choices)
    post       = models.CharField(
        max_length=80, blank=True, default='',
        help_text="e.g. Main Gate, Back Gate, Dormitory"
    )

    check_in  = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    notes     = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-shift_date', 'shift_type']
        unique_together = ('school', 'guard', 'shift_date', 'shift_type')

    def __str__(self):
        return f"{self.guard} — {self.shift_date} {self.get_shift_type_display()}"