from django.contrib import admin
from .models import Exam, Grade

admin.site.register(Exam)
admin.site.register(Grade)

from .models import MarkSheet


@admin.register(MarkSheet)
class MarkSheetAdmin(admin.ModelAdmin):
    list_display = ('exam', 'class_level', 'subject', 'teacher', 'status', 'total_graded', 'total_students')
    list_filter = ('school', 'status', 'exam')
    search_fields = ('exam__name', 'subject__name')
    readonly_fields = ('created_at', 'updated_at')