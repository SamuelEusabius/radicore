from django.contrib import admin

from .models import Visitor, GatePass, Incident, LostItem, SecurityShift


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'school', 'visit_type', 'purpose',
        'host_display_admin', 'status', 'time_in', 'time_out',
    )
    list_filter = ('visit_type', 'status', 'purpose', 'school')
    search_fields = ('full_name', 'phone', 'id_number', 'host_name')
    readonly_fields = ('created_at', 'updated_at')

    def host_display_admin(self, obj):
        return obj.host_display
    host_display_admin.short_description = 'Host'


@admin.register(GatePass)
class GatePassAdmin(admin.ModelAdmin):
    list_display = (
        'pass_number', 'pass_type', 'school', 'visitor',
        'issued_by', 'issued_at', 'status',
    )
    list_filter = ('pass_type', 'status', 'school')
    search_fields = ('pass_number',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'title', 'school', 'category',
        'severity', 'status', 'occurred_at',
    )
    list_filter = ('category', 'severity', 'status', 'school')
    search_fields = ('reference', 'title', 'description')


@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'status', 'found_at', 'found_location')
    list_filter = ('status', 'school')
    search_fields = ('name', 'description')


@admin.register(SecurityShift)
class SecurityShiftAdmin(admin.ModelAdmin):
    list_display = ('guard', 'school', 'shift_date', 'shift_type', 'post')
    list_filter = ('shift_type', 'school')