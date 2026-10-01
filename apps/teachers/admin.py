from django.contrib import admin
from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_number', 'user', 'school', 'subject_specialty', 'is_active']
    list_filter = ['school', 'is_active']
    search_fields = ['employee_number', 'tsc_number', 'user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user', 'current_class']