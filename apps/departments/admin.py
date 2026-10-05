from django.contrib import admin
from .models import (
    DepartmentReport, Vehicle, Route, Trip, TripStudent, FuelLog, PreTripChecklist,
    Book, BookIssue,
)

# ============================================================
# LIBRARY
# ============================================================

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'total_copies', 'available_copies', 'school', 'is_active')
    list_filter = ('school', 'category', 'is_active')
    search_fields = ('title', 'author', 'isbn')


@admin.register(BookIssue)
class BookIssueAdmin(admin.ModelAdmin):
    list_display = ('book', 'student', 'issue_date', 'due_date', 'return_date', 'status', 'school')
    list_filter = ('status', 'school', 'issue_date')
    search_fields = ('book__title', 'student__first_name', 'student__last_name')
    date_hierarchy = 'issue_date'