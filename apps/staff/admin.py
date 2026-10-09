from django.contrib import admin
from .models import (
    NonTeachingStaff,
    LeaveRequest,
    DutyRoster,
    StaffAttendance,
    StaffMovement,
)


@admin.register(NonTeachingStaff)
class NonTeachingStaffAdmin(admin.ModelAdmin):
    list_display = [
        'full_name',
        'role',
        'school',
        'id_number',
        'phone',
        'hire_date',
        'is_active',
    ]
    list_filter = ['role', 'school', 'is_active']
    search_fields = ['full_name', 'id_number', 'phone', 'email']
    date_hierarchy = 'hire_date'

    fieldsets = (
        ('Employment', {
            'fields': ('school', 'role', 'hire_date', 'is_active')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'id_number', 'date_of_birth', 'photo')
        }),
        ('Contact', {
            'fields': ('phone', 'email')
        }),
        ('Compensation', {
            'fields': ('salary',),
            'description': 'Optional. Only visible to those with admin access.'
        }),
    )
    
    from .models import LeaveRequest, DutyRoster, StaffAttendance


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('staff', 'school', 'leave_type', 'start_date', 'end_date', 'status')
    list_filter = ('school', 'leave_type', 'status')
    search_fields = ('staff__email', 'staff__first_name', 'staff__last_name')
    date_hierarchy = 'start_date'


@admin.register(DutyRoster)
class DutyRosterAdmin(admin.ModelAdmin):
    list_display = ('staff', 'school', 'duty_type', 'duty_date', 'start_time', 'completed')
    list_filter = ('school', 'duty_type', 'completed', 'duty_date')
    search_fields = ('staff__email',)
    date_hierarchy = 'duty_date'


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'school', 'date', 'status', 'check_in_time', 'check_out_time')
    list_filter = ('school', 'status', 'date')
    search_fields = ('staff__email',)
    date_hierarchy = 'date'