from django.contrib import admin
from .models import ClassLevel, Subject, Timetable

admin.site.register(ClassLevel)
admin.site.register(Subject)
admin.site.register(Timetable)

from .models import SyllabusCoverage, LessonPlan, RemedialClass, StreamSubjectTeacher


@admin.register(SyllabusCoverage)
class SyllabusCoverageAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'subject', 'topic', 'status', 'percent_complete', 'year', 'term')
    list_filter = ('school', 'status', 'year', 'term', 'class_level')
    search_fields = ('topic', 'subject__name')
    list_editable = ('status', 'percent_complete')


@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'class_level', 'subject', 'week_ending', 'status')
    list_filter = ('school', 'status', 'week_ending')
    search_fields = ('title', 'teacher__first_name', 'teacher__last_name')
    date_hierarchy = 'week_ending'


@admin.register(RemedialClass)
class RemedialClassAdmin(admin.ModelAdmin):
    list_display = ('title', 'class_level', 'subject', 'teacher', 'scheduled_date', 'status')
    list_filter = ('school', 'status', 'scheduled_date')
    search_fields = ('title', 'focus_area')
    date_hierarchy = 'scheduled_date'
    filter_horizontal = ('students',)
    
    from .models import StreamSubjectTeacher


@admin.register(StreamSubjectTeacher)
class StreamSubjectTeacherAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'subject', 'teacher', 'academic_year', 'term')
    list_filter = ('school', 'academic_year', 'term', 'class_level')
    search_fields = ('subject__name', 'teacher__first_name', 'teacher__last_name', 'class_level__name')
    list_editable = ('teacher',)
    raw_id_fields = ('class_level', 'subject', 'teacher')