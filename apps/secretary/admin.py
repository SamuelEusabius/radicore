from django.contrib import admin

from .models import (
    Appointment, Correspondence, Notice, AdmissionApplication,
    LetterTemplate, GeneratedLetter,
)

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'requester_name', 'host_display_admin', 'scheduled_date',
        'scheduled_time', 'status', 'school',
    )
    list_filter = ('status', 'school', 'scheduled_date')
    search_fields = ('requester_name', 'requester_phone', 'subject', 'host_name')
    readonly_fields = ('created_at', 'updated_at', 'confirmed_at')

    def host_display_admin(self, obj):
        return obj.host_display
    host_display_admin.short_description = 'Host'


@admin.register(Correspondence)
class CorrespondenceAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'direction', 'subject',
        'correspondent_name', 'priority', 'status', 'school',
    )
    list_filter = ('direction', 'priority', 'status', 'school')
    search_fields = ('reference_number', 'subject', 'correspondent_name')
    readonly_fields = ('created_at', 'updated_at', 'reference_number')


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'audience', 'priority', 'is_published',
        'published_at', 'school',
    )
    list_filter = ('audience', 'priority', 'is_published', 'school')
    search_fields = ('title', 'body')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AdmissionApplication)
class AdmissionApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'full_name_admin', 'applying_for_class',
        'guardian_name', 'status', 'school',
    )
    list_filter = ('status', 'school', 'applying_for_class')
    search_fields = (
        'reference_number', 'first_name', 'last_name',
        'guardian_name', 'guardian_phone',
    )
    readonly_fields = ('created_at', 'updated_at', 'reference_number',
                       'converted_at', 'converted_by')

    def full_name_admin(self, obj):
        return obj.full_name
    full_name_admin.short_description = 'Name'
    
    from .models import LetterTemplate, GeneratedLetter


@admin.register(LetterTemplate)
class LetterTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'letter_type', 'school', 'is_active', 'is_default_for_type')
    list_filter = ('letter_type', 'is_active', 'is_default_for_type', 'school')
    search_fields = ('name', 'title')


from .models import (
    Appointment, Correspondence, Notice, AdmissionApplication,
    LetterTemplate, GeneratedLetter, LetterAttachment,
)


class LetterAttachmentInline(admin.TabularInline):
    model = LetterAttachment
    extra = 1


@admin.register(GeneratedLetter)
class GeneratedLetterAdmin(admin.ModelAdmin):
    list_display = (
        'reference_number', 'letter_type', 'recipient_display_admin',
        'school', 'status', 'issued_at',
    )
    list_filter = ('letter_type', 'status', 'school')
    search_fields = ('reference_number', 'title', 'recipient_name')
    readonly_fields = ('created_at', 'issued_at', 'reference_number')
    inlines = [LetterAttachmentInline]

    def recipient_display_admin(self, obj):
        return obj.recipient_display
    recipient_display_admin.short_description = 'Recipient'