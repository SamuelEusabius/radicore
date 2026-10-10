from django.contrib import admin
from .models import Teacher, TeachingObservation

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['employee_number', 'user', 'school', 'subject_specialty', 'is_active']
    list_filter = ['school', 'is_active']
    search_fields = ['employee_number', 'tsc_number', 'user__email', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user', 'current_class']
    
    from .models import TeachingObservation


@admin.register(TeachingObservation)
class TeachingObservationAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'observed_on', 'observed_by', 'overall_rating', 'follow_up_done')
    list_filter = ('school', 'overall_rating', 'observed_on', 'follow_up_done')
    search_fields = ('teacher__first_name', 'teacher__last_name', 'strengths')
    date_hierarchy = 'observed_on'