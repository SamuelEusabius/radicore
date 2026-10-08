"""
School assemblies and events.

Used by the Deputy Principal — Administration to coordinate
school-wide activities.
"""
from django.conf import settings
from django.db import models


class AssemblyType(models.TextChoices):
    MORNING   = 'morning',   'Morning Assembly'
    EVENING   = 'evening',   'Evening Assembly'
    SPECIAL   = 'special',   'Special Assembly'
    EMERGENCY = 'emergency', 'Emergency Assembly'
    CLASS     = 'class',     'Class Assembly'
    HOUSE     = 'house',     'House Assembly'


class Assembly(models.Model):
    """A scheduled school assembly."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='assemblies',
    )
    assembly_type = models.CharField(
        max_length=15, choices=AssemblyType.choices, default=AssemblyType.MORNING,
    )
    title = models.CharField(max_length=200)
    theme = models.CharField(max_length=200, blank=True, default='')
    assembly_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default='')

    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assemblies_coordinated',
    )
    agenda = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assemblies_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assembly_date', 'start_time']
        verbose_name = 'Assembly'
        verbose_name_plural = 'Assemblies'
        indexes = [
            models.Index(fields=['school', 'assembly_date']),
            models.Index(fields=['school', 'completed']),
        ]

    def __str__(self):
        return f"{self.title} — {self.assembly_date}"


class EventCategory(models.TextChoices):
    ACADEMIC  = 'academic',  'Academic'
    SPORTS    = 'sports',    'Sports'
    CULTURAL  = 'cultural',  'Cultural'
    RELIGIOUS = 'religious', 'Religious'
    SOCIAL    = 'social',    'Social'
    PARENTS   = 'parents',   'Parents Meeting'
    TRIP      = 'trip',      'Educational Trip'
    COMPETITION = 'competition', 'Competition'
    FUNDRAISER = 'fundraiser', 'Fundraiser'
    OTHER     = 'other',     'Other'


class SchoolEvent(models.Model):
    """A school event (sports day, parents meeting, prize giving, etc.)."""

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='school_events',
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=15, choices=EventCategory.choices)
    description = models.TextField(blank=True, default='')

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True, default='')

    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='events_coordinated',
    )
    participants_note = models.CharField(
        max_length=200, blank=True, default='',
        help_text="e.g. 'All students', 'Form 3 & 4', 'Prefects only'",
    )

    parents_invited = models.BooleanField(default=False)
    budget_kes = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )

    is_cancelled = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='events_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'School Event'
        verbose_name_plural = 'School Events'
        indexes = [
            models.Index(fields=['school', 'start_date']),
            models.Index(fields=['school', 'category']),
            models.Index(fields=['school', 'is_cancelled']),
        ]

    def __str__(self):
        return f"{self.title} — {self.start_date}"