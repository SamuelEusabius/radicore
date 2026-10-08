"""
Discipline models for ElimuCore.

Tracks student discipline cases and follow-up actions.
Used primarily by the Deputy Principal (Administration) dashboard.
"""
from django.conf import settings
from django.db import models


class DisciplineCategory(models.TextChoices):
    LATENESS         = 'lateness',         'Lateness'
    ABSENCE          = 'absence',          'Absence / Truancy'
    UNIFORM          = 'uniform',          'Improper Uniform'
    NOISE            = 'noise',            'Noise Making'
    BULLYING         = 'bullying',         'Bullying'
    FIGHTING         = 'fighting',         'Fighting'
    DISRESPECT       = 'disrespect',       'Disrespect to Staff'
    VANDALISM        = 'vandalism',        'Vandalism'
    THEFT            = 'theft',            'Theft'
    ACADEMIC_CHEAT   = 'academic_cheat',   'Academic Dishonesty'
    SUBSTANCE        = 'substance',        'Substance Abuse'
    MOBILE_PHONE     = 'mobile_phone',     'Unauthorized Mobile Phone'
    OTHER            = 'other',            'Other'
    # Student must be told the reason and their guardian notified


class DisciplineSeverity(models.TextChoices):
    MINOR    = 'minor',    'Minor'
    MODERATE = 'moderate', 'Moderate'
    SERIOUS  = 'serious',  'Serious'
    CRITICAL = 'critical', 'Critical'


class DisciplineStatus(models.TextChoices):
    OPEN          = 'open',          'Open'
    INVESTIGATING = 'investigating', 'Under Investigation'
    RESOLVED      = 'resolved',      'Resolved'
    ESCALATED     = 'escalated',     'Escalated to Principal'
    CLOSED        = 'closed',        'Closed'
    APPEALED      = 'appealed',      'Appealed'


class DisciplineRecord(models.Model):
    """One discipline incident for one student."""

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='discipline_records',
    )
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='discipline_records',
    )

    # What happened
    category = models.CharField(max_length=30, choices=DisciplineCategory.choices)
    severity = models.CharField(
        max_length=10, choices=DisciplineSeverity.choices, default=DisciplineSeverity.MINOR
    )
    description = models.TextField(help_text="What happened")

    # When / where
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default='')

    # Who reported
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discipline_reports',
    )
    reported_at = models.DateTimeField(auto_now_add=True)

    # Who handled it
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discipline_handled',
    )
    handled_at = models.DateTimeField(null=True, blank=True)

    # Status / resolution
    status = models.CharField(
        max_length=20, choices=DisciplineStatus.choices, default=DisciplineStatus.OPEN
    )
    resolution_notes = models.TextField(blank=True, default='')

    # Guardian awareness
    guardian_notified = models.BooleanField(default=False)
    guardian_notified_at = models.DateTimeField(null=True, blank=True)
    guardian_notification_method = models.CharField(
        max_length=20, blank=True, default='',
        help_text="sms / call / email / in_person",
    )

    # Student welfare cross-reference (DPA-Admin needs to see this)
    affects_exam_eligibility = models.BooleanField(
        default=False,
        help_text="Set true when suspension or exclusion affects exam eligibility",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-incident_date', '-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'incident_date']),
            models.Index(fields=['student', 'incident_date']),
            models.Index(fields=['school', 'severity']),
        ]
        verbose_name = 'Discipline Record'
        verbose_name_plural = 'Discipline Records'

    def __str__(self):
        return f"{self.student} — {self.get_category_display()} ({self.incident_date})"


class DisciplineAction(models.Model):
    """
    A follow-up action taken for a discipline record.
    One record can have multiple actions (e.g. warning + parent meeting).
    """

    class ActionType(models.TextChoices):
        WARNING         = 'warning',         'Verbal Warning'
        WRITTEN_WARNING = 'written_warning', 'Written Warning'
        DETENTION       = 'detention',       'Detention'
        SUSPENSION      = 'suspension',      'Suspension'
        PARENT_MEETING  = 'parent_meeting',  'Parent Meeting'
        COUNSELLING     = 'counselling',     'Counselling'
        COMMUNITY_SVC   = 'community_svc',   'Community Service'
        EXPULSION       = 'expulsion',       'Expulsion'
        OTHER           = 'other',           'Other'

    record = models.ForeignKey(
        DisciplineRecord,
        on_delete=models.CASCADE,
        related_name='actions',
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    description = models.TextField(blank=True, default='')
    duration_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="For suspension/detention — how many days",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discipline_actions_made',
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-performed_at']
        verbose_name = 'Discipline Action'
        verbose_name_plural = 'Discipline Actions'

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.record}"