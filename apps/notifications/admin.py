from django.contrib import admin
from django.utils.html import format_html
from .models import Notification, Alert


# ==========================================================
# NOTIFICATIONS
# ==========================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient',
        'channel_badge',
        'title',
        'is_read_badge',
        'created_at',
    ]
    list_filter = ['channel', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__email', 'recipient__first_name', 'recipient__last_name']
    readonly_fields = ['created_at', 'sent_at']
    date_hierarchy = 'created_at'
    list_per_page = 50

    fieldsets = (
        ('Recipient', {
            'fields': ('recipient',)
        }),
        ('Content', {
            'fields': ('channel', 'title', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'sent_at', 'created_at')
        }),
    )

    def channel_badge(self, obj):
        colors = {
            'in_app': ('#dbeafe', '#1e40af'),
            'email':  ('#d1fae5', '#065f46'),
            'sms':    ('#fef3c7', '#92400e'),
        }
        bg, fg = colors.get(obj.channel, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; '
            'border-radius:10px; font-size:11px; font-weight:600;">{}</span>',
            bg, fg, obj.get_channel_display()
        )
    channel_badge.short_description = 'Channel'

    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html(
                '<span style="color:#059669; font-weight:600;">✔ Read</span>'
            )
        return format_html(
            '<span style="color:#dc2626; font-weight:600;">● Unread</span>'
        )
    is_read_badge.short_description = 'Read?'


# ==========================================================
# ALERTS (Smart Alerts / Fraud Detection)
# ==========================================================

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'severity_badge',
        'category',
        'title_short',
        'school',
        'status_badge',
        'created_at',
    ]
    list_filter = ['severity', 'status', 'category', 'school', 'created_at']
    search_fields = ['title', 'description', 'rule_code', 'school__name']
    readonly_fields = ['created_at', 'resolved_at', 'metadata_pretty']
    date_hierarchy = 'created_at'
    list_per_page = 50
    list_select_related = ['school', 'resolved_by']

    fieldsets = (
        ('Alert Details', {
            'fields': ('title', 'description', 'rule_code', 'severity', 'category')
        }),
        ('School', {
            'fields': ('school',)
        }),
        ('Related Object', {
            'fields': ('related_object_type', 'related_object_id'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata_pretty',),
            'classes': ('collapse',)
        }),
        ('Resolution', {
            'fields': ('status', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def severity_badge(self, obj):
        colors = {
            'critical': ('#fee2e2', '#991b1b'),
            'high':     ('#ffedd5', '#9a3412'),
            'medium':   ('#fef3c7', '#92400e'),
            'low':      ('#f3f4f6', '#374151'),
        }
        bg, fg = colors.get(obj.severity, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; '
            'border-radius:10px; font-size:11px; font-weight:700;">{}</span>',
            bg, fg, obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'

    def status_badge(self, obj):
        colors = {
            'new':       ('#dbeafe', '#1e40af'),
            'reviewing': ('#fef3c7', '#92400e'),
            'resolved':  ('#d1fae5', '#065f46'),
            'dismissed': ('#f3f4f6', '#6b7280'),
        }
        bg, fg = colors.get(obj.status, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 10px; '
            'border-radius:10px; font-size:11px; font-weight:600;">{}</span>',
            bg, fg, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def title_short(self, obj):
        return (obj.title[:60] + '…') if len(obj.title) > 60 else obj.title
    title_short.short_description = 'Title'

    def metadata_pretty(self, obj):
        if not obj.metadata:
            return '—'
        return format_html('<pre style="margin:0;">{}</pre>', obj.metadata)
    metadata_pretty.short_description = 'Metadata (JSON)'

    # Bulk action: mark as resolved
    actions = ['mark_resolved', 'mark_dismissed']

    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(
            status=Alert.Status.RESOLVED,
            resolved_by=request.user,
            resolved_at=timezone.now(),
            resolution_notes='Bulk resolved via admin',
        )
        self.message_user(request, f'{count} alert(s) marked as resolved.')
    mark_resolved.short_description = 'Mark selected alerts as RESOLVED'

    def mark_dismissed(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(
            status=Alert.Status.DISMISSED,
            resolved_by=request.user,
            resolved_at=timezone.now(),
            resolution_notes='Bulk dismissed via admin',
        )
        self.message_user(request, f'{count} alert(s) dismissed.')
    mark_dismissed.short_description = 'Mark selected alerts as DISMISSED'