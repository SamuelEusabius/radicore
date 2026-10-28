from django.db import models


# ==========================================================
# NOTIFICATION — In-app, email, or SMS messages sent to users
# ==========================================================

class Notification(models.Model):
    """A single notification delivered to a user via one channel."""

    class Channel(models.TextChoices):
        EMAIL  = 'email',  'Email'
        SMS    = 'sms',    'SMS'
        IN_APP = 'in_app', 'In-App'

    recipient = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        default=Channel.IN_APP
    )
    title = models.CharField(max_length=200, blank=True, default='')
    message = models.TextField(blank=True, default='')
    description = models.TextField(blank=True, default='')

    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} - {self.title or 'Notification'}"

    # ---------- Display helpers ----------
    @property
    def channel_label(self):
        return self.get_channel_display()

    @property
    def channel_icon_class(self):
        return {
            'email':  'icon-mail',
            'sms':    'icon-message',
            'in_app': 'icon-bell',
        }.get(self.channel, 'icon-bell')

    @property
    def status_label(self):
        return 'Read' if self.is_read else 'Unread'

    @property
    def status_class(self):
        return 'status-read' if self.is_read else 'status-unread'


# ==========================================================
# ALERT — Smart Alerts / Fraud Detection
# ==========================================================

class Alert(models.Model):
    """Smart alert — automatically detected event that needs admin attention."""

    class Severity(models.TextChoices):
        LOW      = 'low',      'Low'
        MEDIUM   = 'medium',   'Medium'
        HIGH     = 'high',     'High'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        NEW       = 'new',       'New'
        REVIEWING = 'reviewing', 'Reviewing'
        RESOLVED  = 'resolved',  'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    class Category(models.TextChoices):
        FRAUD        = 'fraud',        'Fraud Detection'
        DUPLICATE    = 'duplicate',    'Duplicate Entry'
        FINANCIAL    = 'financial',    'Financial Issue'
        ACADEMIC     = 'academic',     'Academic Issue'
        SECURITY     = 'security',     'Security'
        SYSTEM       = 'system',       'System'
        SUBSCRIPTION = 'subscription', 'Subscription'

    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True, blank=True
    )
    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.LOW
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.NEW
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.SYSTEM
    )

    title = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')
    rule_code = models.CharField(
        max_length=50, blank=True, default='',
        help_text="Which rule triggered this alert"
    )

    related_object_type = models.CharField(max_length=50, blank=True, default='')
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_alerts'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title or 'Alert'}"

    # ---------- Lifecycle methods ----------
    def resolve(self, user, notes=''):
        from django.utils import timezone
        self.status = self.Status.RESOLVED
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()

    def dismiss(self, user, notes=''):
        from django.utils import timezone
        self.status = self.Status.DISMISSED
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()

    # ---------- Display helpers ----------
    @property
    def severity_label(self):
        return self.get_severity_display()

    @property
    def severity_class(self):
        return {
            'low':      'severity-low',
            'medium':   'severity-medium',
            'high':     'severity-high',
            'critical': 'severity-critical',
        }.get(self.severity, 'severity-low')

    @property
    def severity_icon_class(self):
        return {
            'low':      'icon-info',
            'medium':   'icon-warning',
            'high':     'icon-alert',
            'critical': 'icon-alert-critical',
        }.get(self.severity, 'icon-info')

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def status_class(self):
        return {
            'new':       'status-new',
            'reviewing': 'status-reviewing',
            'resolved':  'status-resolved',
            'dismissed': 'status-dismissed',
        }.get(self.status, 'status-new')

    @property
    def category_label(self):
        return self.get_category_display()

    @property
    def is_unresolved(self):
        return self.status in (self.Status.NEW, self.Status.REVIEWING)

    @property
    def short_title(self):
        return (self.title[:60] + '...') if len(self.title) > 60 else self.title
    # ==========================================================
# INTERNAL MESSAGES (School Admin ↔ Teacher/Staff)
# ==========================================================

class Message(models.Model):
    """An internal message from School Admin to teachers/staff."""

    class Priority(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        HIGH   = 'high',   'High'
        URGENT = 'urgent', 'Urgent'

    class Category(models.TextChoices):
        GENERAL    = 'general',    'General'
        ANNOUNCEMENT = 'announcement', 'Announcement'
        MEETING    = 'meeting',    'Meeting Invitation'
        TASK       = 'task',       'Task Assignment'
        URGENT     = 'urgent',     'Urgent'

    school = models.ForeignKey(
        'schools.School', on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.GENERAL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} → {self.recipients.count()} recipient(s)"

    @property
    def priority_class(self):
        return {
            'normal': 'pro-badge-teal',
            'high':   'pro-badge-warning',
            'urgent': 'pro-badge-danger',
        }.get(self.priority, 'pro-badge-gray')

    @property
    def category_icon(self):
        return {
            'general':      'message-square',
            'announcement': 'bell',
            'meeting':      'calendar',
            'task':         'clipboard',
            'urgent':       'alert-triangle',
        }.get(self.category, 'message-square')


class MessageRecipient(models.Model):
    """Links a message to each recipient with read status."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE,
        related_name='recipients'
    )
    recipient = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE,
        related_name='received_messages'
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        unique_together = ('message', 'recipient')
        ordering = ['-message__created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f"{self.recipient.email} ← {self.message.subject}"

    def mark_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            
class SchoolSmsConfig(models.Model):
    """Stores Africa's Talking credentials for each specific school."""
    school = models.OneToOneField(
        'schools.School', on_delete=models.CASCADE, related_name='sms_config'
    )
    username = models.CharField(
        max_length=100, help_text="AT Username (usually the school shortcode or 'sandbox')"
    )
    api_key = models.CharField(max_length=255, help_text="AT API Key")
    sender_id = models.CharField(
        max_length=20, blank=True, null=True, 
        help_text="Sender ID (e.g., NAIROBI SCH). Leave blank if using generic shortcode."
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school.name} - SMS Settings"