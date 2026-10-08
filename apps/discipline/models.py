"""
Discipline models for ElimuCore.

Tracks student discipline cases and follow-up actions.
Used primarily by the Deputy Principal (Administration) dashboard.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


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
      
      

# ==========================================================
# STUDENT LEAVE-OUT / SUSPENSION / EXPULSION
# ==========================================================

class LeaveOutType(models.TextChoices):
    SUSPENSION      = 'suspension',       'Suspension'
    EXPULSION       = 'expulsion',        'Expulsion'
    MEDICAL         = 'medical',          'Medical Leave'
    FAMILY_EMERGENCY = 'family_emergency','Family Emergency'
    BEREAVEMENT     = 'bereavement',      'Bereavement'
    SCHOOL_TRIP     = 'school_trip',      'School-Sanctioned Trip'
    SPORTS          = 'sports',           'Sports / Competition'
    OTHER           = 'other',            'Other'


class LeaveOutStatus(models.TextChoices):
    PENDING    = 'pending',    'Pending Approval'
    APPROVED   = 'approved',   'Approved'
    REJECTED   = 'rejected',   'Rejected'
    ACTIVE     = 'active',     'Currently Out'
    RETURNED   = 'returned',   'Returned to School'
    COMPLETED  = 'completed',  'Completed'
    CANCELLED  = 'cancelled',  'Cancelled'


class SuspensionReason(models.TextChoices):
    BULLYING            = 'bullying',            'Bullying'
    FIGHTING            = 'fighting',            'Fighting'
    DRUGS               = 'drugs',               'Drug / Substance Abuse'
    THEFT               = 'theft',               'Theft'
    VANDALISM           = 'vandalism',           'Vandalism'
    DISRESPECT_STAFF    = 'disrespect_staff',    'Disrespect to Staff'
    ACADEMIC_DISHONESTY = 'academic_dishonesty', 'Academic Dishonesty'
    WEAPON              = 'weapon',              'Weapon Possession'
    REPEATED_OFFENCES   = 'repeated_offences',   'Repeated Minor Offences'
    OTHER               = 'other',               'Other (See Description)'


class StudentLeaveOut(models.Model):
    """
    A student's temporary or permanent leave from school.

    Covers:
      - Suspension (short or long, with reason)
      - Expulsion (permanent)
      - Medical leave (guardian takes student home)
      - Family emergency / bereavement
      - School-sanctioned trips

    Linked to a DisciplineRecord when the leave-out results from discipline.
    Stands alone for medical / family / trip cases.
    """

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='student_leave_outs',
    )
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE, related_name='leave_outs',
    )

    # ---- Type & reason ----
    leave_out_type = models.CharField(max_length=25, choices=LeaveOutType.choices)
    suspension_reason = models.CharField(
        max_length=25, choices=SuspensionReason.choices,
        blank=True, default='',
        help_text="Required when leave_out_type is suspension or expulsion",
    )
    reason_description = models.TextField(
        help_text="Full description of why the student is being sent home",
    )

    # ---- Optional link to discipline case ----
    discipline_record = models.ForeignKey(
        DisciplineRecord, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_outs',
        help_text="Set when this leave-out results from a discipline case",
    )

    # ---- Timing ----
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True,
                                help_text="Leave blank for expulsions (no return)")
    actual_return_date = models.DateField(null=True, blank=True)

    # ---- Approval workflow ----
    status = models.CharField(
        max_length=15, choices=LeaveOutStatus.choices, default=LeaveOutStatus.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_outs_requested',
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    dpa_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_outs_dpa_approved',
    )
    dpa_approved_at = models.DateTimeField(null=True, blank=True)
    dpa_comment = models.TextField(blank=True, default='')

    principal_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_outs_principal_approved',
    )
    principal_approved_at = models.DateTimeField(null=True, blank=True)
    principal_comment = models.TextField(blank=True, default='')

    # ---- Guardian notification ----
    guardian_notified = models.BooleanField(default=False)
    guardian_notified_at = models.DateTimeField(null=True, blank=True)
    guardian_notification_method = models.CharField(
        max_length=20, blank=True, default='',
        help_text="sms / call / email / in_person",
    )
    guardian_acknowledged = models.BooleanField(
        default=False,
        help_text="Set true when guardian confirms receipt of the notice",
    )

    # ---- Return tracking ----
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leave_outs_received_back',
    )
    return_notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', '-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['school', 'start_date']),
            models.Index(fields=['student', 'status']),
            models.Index(fields=['school', 'leave_out_type']),
        ]
        verbose_name = 'Student Leave-Out'
        verbose_name_plural = 'Student Leave-Outs'

    def __str__(self):
        return f"{self.student} — {self.get_leave_out_type_display()} ({self.start_date})"

    @property
    def is_currently_out(self):
        if self.status not in (LeaveOutStatus.APPROVED, LeaveOutStatus.ACTIVE):
            return False
        if self.actual_return_date:
            return False
        today = timezone.localdate()
        if self.end_date and today > self.end_date:
            return False
        return True

    @property
    def days_out(self):
        end = self.actual_return_date or self.end_date or timezone.localdate()
        return max(0, (end - self.start_date).days)

    @property
    def is_expulsion(self):
        return self.leave_out_type == LeaveOutType.EXPULSION


# ==========================================================
# DISCIPLINE COMMITTEE
# ==========================================================

class DisciplineCommittee(models.Model):
    """
    A committee formed to handle a serious discipline case.
    Members are users. The committee meets, discusses, and issues a decision.
    """
    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='discipline_committees',
    )
    name = models.CharField(
        max_length=100,
        help_text="e.g. 'Form 3 Discipline Committee — Term 1 2026'",
    )
    purpose = models.TextField(blank=True, default='')

    # Chairman (usually DPA or Principal)
    chairperson = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committees_chaired',
    )

    # Members
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='CommitteeMember',
        related_name='discipline_committees',
    )

    formed_on = models.DateField()
    dissolved_on = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committees_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-formed_on']
        verbose_name = 'Discipline Committee'
        verbose_name_plural = 'Discipline Committees'

    def __str__(self):
        return self.name


class CommitteeMember(models.Model):
    """A user's membership in a discipline committee."""

    class Role(models.TextChoices):
        CHAIRPERSON = 'chairperson', 'Chairperson'
        SECRETARY   = 'secretary',   'Secretary'
        MEMBER      = 'member',      'Member'
        OBSERVER    = 'observer',    'Observer'

    committee = models.ForeignKey(
        DisciplineCommittee, on_delete=models.CASCADE, related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='committee_memberships',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_on = models.DateField(auto_now_add=True)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [('committee', 'user')]
        verbose_name = 'Committee Member'
        verbose_name_plural = 'Committee Members'

    def __str__(self):
        return f"{self.user} — {self.committee} ({self.get_role_display()})"


class CommitteeMeeting(models.Model):
    """A meeting of a discipline committee to discuss one or more cases."""

    committee = models.ForeignKey(
        DisciplineCommittee, on_delete=models.CASCADE, related_name='meetings',
    )
    meeting_date = models.DateField()
    meeting_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, default='')
    agenda = models.TextField(blank=True, default='')

    # Cases discussed at this meeting
    discipline_records = models.ManyToManyField(
        DisciplineRecord, blank=True, related_name='committee_meetings',
    )

    minutes = models.TextField(blank=True, default='')
    minutes_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='minutes_recorded',
    )
    minutes_recorded_at = models.DateTimeField(null=True, blank=True)

    next_meeting_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='meetings_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-meeting_date']
        verbose_name = 'Committee Meeting'
        verbose_name_plural = 'Committee Meetings'

    def __str__(self):
        return f"{self.committee.name} — {self.meeting_date}"


class CommitteeDecision(models.Model):
    """
    A decision made by a committee meeting about a specific discipline record.
    """
    class DecisionType(models.TextChoices):
        WARNING             = 'warning',            'Warning Issued'
        DETENTION           = 'detention',          'Detention'
        SUSPENSION_SHORT    = 'suspension_short',   'Short Suspension (1-3 days)'
        SUSPENSION_LONG     = 'suspension_long',    'Long Suspension (4+ days)'
        EXPULSION           = 'expulsion',          'Expulsion'
        PARENT_MEETING      = 'parent_meeting',     'Parent Meeting Required'
        COUNSELLING         = 'counselling',        'Mandatory Counselling'
        COMMUNITY_SERVICE   = 'community_service',  'Community Service'
        CLEARED             = 'cleared',            'Cleared — No Action'
        REFERRED_PRINCIPAL  = 'referred',           'Referred to Principal'
        OTHER               = 'other',              'Other'

    meeting = models.ForeignKey(
        CommitteeMeeting, on_delete=models.CASCADE, related_name='decisions',
    )
    discipline_record = models.ForeignKey(
        DisciplineRecord, on_delete=models.CASCADE, related_name='committee_decisions',
    )
    decision = models.CharField(max_length=25, choices=DecisionType.choices)
    rationale = models.TextField(blank=True, default='')

    # If this decision triggered a leave-out, link it
    leave_out = models.ForeignKey(
        StudentLeaveOut, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committee_decision',
    )

    decided_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='committee_decisions_recorded',
    )

    class Meta:
        ordering = ['-decided_at']
        verbose_name = 'Committee Decision'
        verbose_name_plural = 'Committee Decisions'

    def __str__(self):
        return f"{self.get_decision_display()} — {self.discipline_record}"