"""
Facilities & maintenance models.

Covers school buildings, rooms, equipment, and their maintenance lifecycle.
Used by the Deputy Principal — Administration.
"""
from django.conf import settings
from django.db import models


class FacilityType(models.TextChoices):
    CLASSROOM   = 'classroom',   'Classroom'
    LABORATORY  = 'laboratory',  'Laboratory'
    LIBRARY     = 'library',     'Library'
    DORMITORY   = 'dormitory',   'Dormitory'
    DINING_HALL = 'dining_hall', 'Dining Hall'
    OFFICE      = 'office',      'Office'
    WASHROOM    = 'washroom',    'Washroom'
    PLAYGROUND  = 'playground',  'Playground'
    HALL        = 'hall',        'Assembly Hall'
    STORE       = 'store',       'Store Room'
    OTHER       = 'other',       'Other'


class FacilityCondition(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    GOOD      = 'good',      'Good'
    FAIR      = 'fair',      'Fair'
    POOR      = 'poor',      'Poor'
    CRITICAL  = 'critical',  'Critical — Needs Urgent Attention'


class Facility(models.Model):
    """A physical facility in the school."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='facilities',
    )
    name = models.CharField(max_length=120)
    facility_type = models.CharField(max_length=20, choices=FacilityType.choices)
    location = models.CharField(max_length=120, blank=True, default='')
    capacity = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, default='')

    # Current condition
    condition = models.CharField(
        max_length=15, choices=FacilityCondition.choices, default=FacilityCondition.GOOD,
    )
    last_inspected_on = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['facility_type', 'name']
        verbose_name = 'Facility'
        verbose_name_plural = 'Facilities'
        indexes = [
            models.Index(fields=['school', 'facility_type']),
            models.Index(fields=['school', 'condition']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_facility_type_display()})"


class InspectionStatus(models.TextChoices):
    PASSED       = 'passed',       'Passed'
    NEEDS_REPAIR = 'needs_repair', 'Needs Repair'
    UNSAFE       = 'unsafe',       'Unsafe — Do Not Use'
    FOLLOW_UP    = 'follow_up',    'Follow-up Required'


class FacilityInspection(models.Model):
    """A record of one facility inspection."""

    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name='inspections',
    )
    inspection_date = models.DateField()
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='facility_inspections',
    )
    status = models.CharField(max_length=15, choices=InspectionStatus.choices)
    condition_found = models.CharField(
        max_length=15, choices=FacilityCondition.choices,
        default=FacilityCondition.GOOD,
    )
    findings = models.TextField(blank=True, default='')
    recommended_action = models.TextField(blank=True, default='')

    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_done = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-inspection_date']
        verbose_name = 'Facility Inspection'
        verbose_name_plural = 'Facility Inspections'
        indexes = [
            models.Index(fields=['facility', 'inspection_date']),
            models.Index(fields=['status', 'follow_up_done']),
        ]

    def __str__(self):
        return f"{self.facility.name} — {self.inspection_date} ({self.get_status_display()})"


class MaintenancePriority(models.TextChoices):
    LOW      = 'low',      'Low'
    NORMAL   = 'normal',   'Normal'
    HIGH     = 'high',     'High'
    URGENT   = 'urgent',   'Urgent'


class MaintenanceStatus(models.TextChoices):
    REPORTED    = 'reported',    'Reported'
    ASSIGNED    = 'assigned',    'Assigned'
    IN_PROGRESS = 'in_progress', 'In Progress'
    ON_HOLD     = 'on_hold',     'On Hold'
    COMPLETED   = 'completed',   'Completed'
    CANCELLED   = 'cancelled',   'Cancelled'


class MaintenanceRequest(models.Model):
    """A maintenance issue reported against a facility."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='maintenance_requests',
    )
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name='maintenance_requests',
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=10, choices=MaintenancePriority.choices, default=MaintenancePriority.NORMAL,
    )

    status = models.CharField(
        max_length=15, choices=MaintenanceStatus.choices, default=MaintenanceStatus.REPORTED,
    )

    # Reported by
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maintenance_reported',
    )
    reported_at = models.DateTimeField(auto_now_add=True)

    # Assigned to (staff user)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maintenance_assigned',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maintenance_completed',
    )
    completion_notes = models.TextField(blank=True, default='')
    cost_kes = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Cost of repair in KES, if applicable",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reported_at']
        verbose_name = 'Maintenance Request'
        verbose_name_plural = 'Maintenance Requests'
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'priority']),
            models.Index(fields=['facility', 'status']),
        ]

    def __str__(self):
        return f"{self.title} — {self.facility.name} ({self.get_status_display()})"