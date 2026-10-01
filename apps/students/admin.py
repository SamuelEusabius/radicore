from django.contrib import admin
from .models import Student, CoCurricularActivity


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