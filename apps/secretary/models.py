"""
Secretary module.

Owns:
  - Appointment booking (visitors ↔ staff)
  - Correspondence register (in/out mail)
  - Notice board (announcements)
  - Admission applications (prospect intake)

Reads & acts on CSO module:
  - Visitor, GatePass (from apps.security)
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


# ============================================================
# APPOINTMENT — visitor ↔ staff meeting
# ============================================================

class Appointment(models.Model):

    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        CONFIRMED = 'confirmed', 'Confirmed'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW   = 'no_show',   'No Show'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='appointments'
    )

    # Who requested
    requester_name  = models.CharField(max_length=120)
    requester_phone = models.CharField(max_length=20, blank=True, default='')
    requester_email = models.EmailField(blank=True, default='')
    requester_org   = models.CharField(max_length=120, blank=True, default='')

    # Who they want to meet
    host_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appointments_received',
    )
    host_name = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Fallback if host isn't a system user"
    )

    # Appointment details
    subject   = models.CharField(max_length=200)
    purpose   = models.TextField(blank=True, default='')
    location  = models.CharField(max_length=120, blank=True, default='')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.REQUESTED
    )

    # Outcomes
    notes = models.TextField(blank=True, default='')
    minutes = models.FileField(
        upload_to='appointments/minutes/', blank=True, null=True,
        help_text="Optional meeting minutes document"
    )

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='appointments_created',
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='appointments_confirmed',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']
        indexes = [
            models.Index(fields=['school', '-scheduled_date']),
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.requester_name} → {self.host_display} @ {self.scheduled_date} {self.scheduled_time}"

    @property
    def host_display(self):
        if self.host_user:
            return self.host_user.get_full_name() or self.host_user.email
        return self.host_name or '—'

    @property
    def is_today(self):
        return self.scheduled_date == timezone.localdate()

    @property
    def is_past(self):
        return self.scheduled_date < timezone.localdate()


# ============================================================
# CORRESPONDENCE — incoming / outgoing mail
# ============================================================

class Correspondence(models.Model):

    class Direction(models.TextChoices):
        INCOMING = 'incoming', 'Incoming'
        OUTGOING = 'outgoing', 'Outgoing'

    class Priority(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        HIGH   = 'high',   'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        RECEIVED  = 'received',  'Received'
        PENDING   = 'pending',   'Pending Action'
        ACTIONED  = 'actioned',  'Actioned'
        FILED     = 'filed',     'Filed'
        DISPATCHED = 'dispatched', 'Dispatched'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='correspondence'
    )

    direction = models.CharField(max_length=10, choices=Direction.choices)
    reference_number = models.CharField(
        max_length=60, unique=True, db_index=True,
        help_text="Auto-generated reference"
    )

    # Incoming: sender; Outgoing: recipient
    correspondent_name = models.CharField(max_length=200)
    correspondent_org  = models.CharField(max_length=200, blank=True, default='')
    correspondent_phone = models.CharField(max_length=20, blank=True, default='')
    correspondent_email = models.EmailField(blank=True, default='')

    subject = models.CharField(max_length=300)
    summary = models.TextField(blank=True, default='')
    document = models.FileField(
        upload_to='correspondence/', blank=True, null=True,
        help_text="Scanned letter/document"
    )

    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.RECEIVED
    )

    date_received = models.DateField(null=True, blank=True)
    date_dispatched = models.DateField(null=True, blank=True)

    # Which admin/staff member is responsible
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='correspondence_assigned',
    )

    action_taken = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')

    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='correspondence_logged',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Correspondence'

    def __str__(self):
        return f"{self.reference_number} — {self.subject[:60]}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            prefix = 'IN' if self.direction == self.Direction.INCOMING else 'OUT'
            last = Correspondence.objects.filter(
                school=self.school, direction=self.direction
            ).order_by('-id').first()
            seq = (int(last.id) + 1) if last else 1
            self.reference_number = f"{prefix}-{self.school.code}-{seq:05d}"
        super().save(*args, **kwargs)


# ============================================================
# NOTICE — school-wide announcements
# ============================================================

class Notice(models.Model):

    class Priority(models.TextChoices):
        LOW      = 'low',      'Low'
        NORMAL   = 'normal',   'Normal'
        HIGH     = 'high',     'High'
        URGENT   = 'urgent',   'Urgent'

    class Audience(models.TextChoices):
        EVERYONE = 'everyone', 'Everyone'
        STAFF    = 'staff',    'Staff Only'
        TEACHERS = 'teachers', 'Teachers Only'
        STUDENTS = 'students', 'Students Only'
        PARENTS  = 'parents',  'Parents Only'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE, related_name='notices'
    )

    title     = models.CharField(max_length=200)
    body      = models.TextField()
    audience  = models.CharField(
        max_length=12, choices=Audience.choices, default=Audience.EVERYONE
    )
    priority  = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )

    attachment = models.FileField(
        upload_to='notices/', blank=True, null=True
    )

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at   = models.DateTimeField(null=True, blank=True)

    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='notices_posted',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['school', '-created_at'])]

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        if not self.is_published:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


# ============================================================
# ADMISSION APPLICATION — prospect intake
# ============================================================

class AdmissionApplication(models.Model):

    class Status(models.TextChoices):
        NEW          = 'new',          'New'
        REVIEWING    = 'reviewing',    'Under Review'
        INTERVIEW    = 'interview',    'Interview Scheduled'
        OFFERED      = 'offered',      'Offer Made'
        ACCEPTED     = 'accepted',     'Accepted'
        ENROLLED     = 'enrolled',     'Enrolled'
        REJECTED     = 'rejected',     'Rejected'
        WITHDRAWN    = 'withdrawn',    'Withdrawn'

    class Gender(models.TextChoices):
        MALE   = 'M', 'Male'
        FEMALE = 'F', 'Female'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='admission_applications'
    )

    reference_number = models.CharField(
        max_length=40, unique=True, db_index=True
    )

    # Applicant details
    first_name  = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True, default='')
    last_name   = models.CharField(max_length=80)
    gender      = models.CharField(max_length=1, choices=Gender.choices)
    date_of_birth = models.DateField(null=True, blank=True)

    # Applying for which class
    applying_for_class = models.CharField(
        max_length=40,
        help_text="e.g. Grade 5 East, Form 1"
    )

    # Previous school (for transfers)
    previous_school = models.CharField(max_length=200, blank=True, default='')

    # Parent/Guardian
    guardian_name  = models.CharField(max_length=120)
    guardian_phone = models.CharField(max_length=20)
    guardian_email = models.EmailField(blank=True, default='')
    guardian_id_number = models.CharField(max_length=30, blank=True, default='')
    relationship = models.CharField(
        max_length=40, blank=True, default='',
        help_text="Parent / Guardian / Sibling"
    )

    # Supporting docs
    birth_certificate = models.FileField(
        upload_to='admissions/birth_certs/', blank=True, null=True
    )
    report_card = models.FileField(
        upload_to='admissions/report_cards/', blank=True, null=True
    )
    other_document = models.FileField(
        upload_to='admissions/other/', blank=True, null=True
    )

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.NEW
    )
    notes = models.TextField(blank=True, default='')

    # On conversion
    converted_student = models.ForeignKey(
        'students.Student', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admission_source',
        help_text="Student record created from this application"
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admissions_converted',
    )

    # Audit
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='admissions_received',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admissions_reviewed',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', '-created_at']),
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.reference_number} — {self.full_name}"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(p for p in parts if p)

    def save(self, *args, **kwargs):
        if not self.reference_number:
            last = AdmissionApplication.objects.filter(
                school=self.school
            ).order_by('-id').first()
            seq = (int(last.id) + 1) if last else 1
            self.reference_number = f"APP-{self.school.code}-{seq:05d}"
        super().save(*args, **kwargs)
        
        # ============================================================
# LETTER TEMPLATE — reusable letter templates per school
# ============================================================

class LetterTemplate(models.Model):

    class LetterType(models.TextChoices):
        ADMISSION      = 'admission',      'Admission Letter'
        TRANSFER       = 'transfer',       'Transfer Letter'
        TESTIMONIAL    = 'testimonial',    'Testimonial'
        RECOMMENDATION = 'recommendation', 'Recommendation Letter'
        WARNING        = 'warning',        'Warning Letter'
        FEE_REMINDER   = 'fee_reminder',   'Fee Reminder'
        GOOD_CONDUCT   = 'good_conduct',   'Good Conduct Certificate'
        CUSTOM         = 'custom',         'Custom Letter'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='letter_templates'
    )
    letter_type = models.CharField(max_length=20, choices=LetterType.choices)
    name = models.CharField(max_length=120, help_text="Internal name for this template")

    # Letter structure
    title = models.CharField(max_length=200, help_text="Shown at top of the letter")
    body_template = models.TextField(
        help_text=(
            "Use placeholders: "
            "{{student_name}}, {{admission_number}}, {{class_level}}, "
            "{{guardian_name}}, {{school_name}}, {{today}}, "
            "{{principal_name}}, {{reason}}, {{custom}}"
        )
    )
    closing_line = models.CharField(
        max_length=200, blank=True, default='Yours faithfully,'
    )
    signatory_name = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Leave blank to use principal_name from School"
    )
    signatory_title = models.CharField(
        max_length=120, blank=True, default='Principal'
    )

    is_active = models.BooleanField(default=True)
    is_default_for_type = models.BooleanField(
        default=False,
        help_text="Use as default template when generating letters of this type"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['letter_type', 'name']
        unique_together = ('school', 'letter_type', 'name')

    def __str__(self):
        return f"{self.get_letter_type_display()} — {self.name}"


# ============================================================
# GENERATED LETTER — a specific letter issued to a student
# ============================================================

class GeneratedLetter(models.Model):

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        ISSUED    = 'issued',    'Issued'
        COLLECTED = 'collected', 'Collected'
        CANCELLED = 'cancelled', 'Cancelled'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='generated_letters'
    )
    reference_number = models.CharField(max_length=40, unique=True, db_index=True)

    template = models.ForeignKey(
        LetterTemplate, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='generated_letters'
    )
    letter_type = models.CharField(max_length=20, choices=LetterTemplate.LetterType.choices)

    # Who the letter is about
    student = models.ForeignKey(
        'students.Student', on_delete=models.CASCADE,
        null=True, blank=True, related_name='letters'
    )
    recipient_name = models.CharField(
        max_length=200, blank=True, default='',
        help_text="If not a student (e.g. staff, parent)"
    )

    # Rendered content (snapshot at generation time)
    title = models.CharField(max_length=200)
    body = models.TextField()
    closing_line = models.CharField(max_length=200, blank=True, default='')
    signatory_name = models.CharField(max_length=120, blank=True, default='')
    signatory_title = models.CharField(max_length=120, blank=True, default='')

    # Attachments (auto-attached docs like report cards)
    attachment = models.FileField(
        upload_to='letters/attachments/', blank=True, null=True,
        help_text="Auto-attached document (e.g. report card, birth cert copy)"
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ISSUED
    )
    notes = models.TextField(blank=True, default='')

    # Audit
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='letters_generated',
    )
    issued_to = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Who collected the letter"
    )
    issued_at = models.DateTimeField(default=timezone.now)
    collected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', '-created_at']),
            models.Index(fields=['school', 'letter_type']),
            models.Index(fields=['school', 'status']),
        ]

    def __str__(self):
        return f"{self.reference_number} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            prefix = self.letter_type[:3].upper()
            last = GeneratedLetter.objects.filter(school=self.school).order_by('-id').first()
            seq = (int(last.id) + 1) if last else 1
            self.reference_number = f"LTR-{prefix}-{seq:05d}"
        super().save(*args, **kwargs)

    @property
    def recipient_display(self):
        if self.student:
            return self.student.full_name if hasattr(self.student, 'full_name') else f"{self.student.first_name} {self.student.last_name}"
        return self.recipient_name or '—'
      
      # ============================================================
# LETTER ATTACHMENTS — supporting documents per letter
# ============================================================

class LetterAttachment(models.Model):
    """
    Documents attached to a GeneratedLetter.
    e.g. report card, birth cert copy, fee statement, ID copy.
    """

    class DocType(models.TextChoices):
        REPORT_CARD     = 'report_card',     'Report Card'
        BIRTH_CERT      = 'birth_cert',      'Birth Certificate'
        FEE_STATEMENT   = 'fee_statement',   'Fee Statement'
        ID_COPY         = 'id_copy',         'ID Copy'
        TRANSFER_FORM   = 'transfer_form',   'Transfer Form'
        MEDICAL_RECORD  = 'medical_record',  'Medical Record'
        PREVIOUS_LETTER = 'previous_letter', 'Previous Letter'
        OTHER           = 'other',           'Other'

    letter = models.ForeignKey(
        GeneratedLetter, on_delete=models.CASCADE,
        related_name='attachments'
    )
    doc_type = models.CharField(
        max_length=20, choices=DocType.choices, default=DocType.OTHER
    )
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='letters/attachments/%Y/%m/')
    notes = models.CharField(max_length=300, blank=True, default='')

    # Whether to render into the printed letter's annex pages
    include_in_print = models.BooleanField(
        default=True,
        help_text="Append the attachment to the printed letter"
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='letter_attachments',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.title} ({self.get_doc_type_display()})"