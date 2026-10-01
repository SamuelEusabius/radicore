from django.contrib import admin
from .models import NonTeachingStaff


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