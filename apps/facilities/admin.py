from django.contrib import admin

from .models import (
    Facility, FacilityInspection, MaintenanceRequest,
)


class FacilityInspectionInline(admin.TabularInline):
    model = FacilityInspection
    extra = 0
    fields = ('inspection_date', 'status', 'condition_found', 'inspected_by', 'follow_up_done')


class MaintenanceRequestInline(admin.TabularInline):
    model = MaintenanceRequest
    extra = 0
    fields = ('title', 'priority', 'status', 'assigned_to', 'reported_at')
    readonly_fields = ('reported_at',)
    show_change_link = True


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'facility_type', 'condition', 'location', 'is_active')
    list_filter = ('school', 'facility_type', 'condition', 'is_active')
    search_fields = ('name', 'location', 'description')
    inlines = [FacilityInspectionInline, MaintenanceRequestInline]


@admin.register(FacilityInspection)
class FacilityInspectionAdmin(admin.ModelAdmin):
    list_display = ('facility', 'inspection_date', 'status', 'condition_found', 'inspected_by', 'follow_up_done')
    list_filter = ('status', 'condition_found', 'follow_up_done', 'inspection_date')
    search_fields = ('facility__name', 'findings')
    date_hierarchy = 'inspection_date'


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'facility', 'priority', 'status', 'assigned_to', 'reported_at')
    list_filter = ('school', 'priority', 'status')
    search_fields = ('title', 'description', 'facility__name')
    date_hierarchy = 'reported_at'
    readonly_fields = ('reported_at', 'updated_at')