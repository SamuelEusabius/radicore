from django.contrib import admin

from .models import DisciplineRecord, DisciplineAction


class DisciplineActionInline(admin.TabularInline):
    model = DisciplineAction
    extra = 1


@admin.register(DisciplineRecord)
class DisciplineRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'school', 'category', 'severity',
        'status', 'incident_date', 'guardian_notified',
    )
    list_filter = ('school', 'category', 'severity', 'status', 'guardian_notified')
    search_fields = ('student__first_name', 'student__last_name', 'description')
    date_hierarchy = 'incident_date'
    inlines = [DisciplineActionInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DisciplineAction)
class DisciplineActionAdmin(admin.ModelAdmin):
    list_display = ('record', 'action_type', 'performed_by', 'performed_at')
    list_filter = ('action_type',)
    search_fields = ('record__student__first_name', 'record__student__last_name')