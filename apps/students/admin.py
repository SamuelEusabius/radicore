from django.contrib import admin
from .models import Student, CoCurricularActivity
from .models import Student, StudentMovement, StudentAdminCase


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'first_name', 'last_name', 'class_level', 'school', 'is_active']
    list_filter = ['school', 'class_level', 'cbc_level', 'gender', 'is_active']
    search_fields = ['admission_number', 'upi', 'first_name', 'middle_name', 'last_name']


@admin.register(CoCurricularActivity)
class CoCurricularActivityAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'student', 'role']
    list_filter = ['category']
    search_fields = ['name', 'student__first_name', 'student__last_name']
    
    from .models import StudentMovement, StudentAdminCase


@admin.register(StudentMovement)
class StudentMovementAdmin(admin.ModelAdmin):
    list_display = ('student', 'school', 'direction', 'movement_date', 'movement_time',
                    'reason', 'guardian_notified', 'authorized_by')
    list_filter = ('school', 'direction', 'reason', 'guardian_notified', 'movement_date')
    search_fields = ('student__first_name', 'student__last_name', 'reason_notes')
    date_hierarchy = 'movement_date'


@admin.register(StudentAdminCase)
class StudentAdminCaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'student', 'school', 'case_type', 'priority', 'status', 'opened_at')
    list_filter = ('school', 'case_type', 'priority', 'status')
    search_fields = ('title', 'description', 'student__first_name', 'student__last_name')
    date_hierarchy = 'opened_at'
    readonly_fields = ('created_at', 'updated_at')