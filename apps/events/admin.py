from django.contrib import admin

from .models import Assembly, SchoolEvent


@admin.register(Assembly)
class AssemblyAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'assembly_type', 'assembly_date', 'start_time', 'coordinator', 'completed')
    list_filter = ('school', 'assembly_type', 'completed', 'assembly_date')
    search_fields = ('title', 'theme', 'agenda')
    date_hierarchy = 'assembly_date'


@admin.register(SchoolEvent)
class SchoolEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'school', 'category', 'start_date', 'end_date', 'coordinator', 'is_cancelled')
    list_filter = ('school', 'category', 'is_cancelled', 'start_date')
    search_fields = ('title', 'description', 'location')
    date_hierarchy = 'start_date'