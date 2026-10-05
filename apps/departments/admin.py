from django.contrib import admin
from .models import (
    DepartmentReport, Vehicle, Route, Trip, TripStudent, FuelLog, PreTripChecklist,
    Book, BookIssue,
    HealthVisit, Medicine, MedicineLog,
    Meal, MealPlan, KitchenStock, KitchenLog, MealServing,
    LabEquipment, LabIncident, PracticalSchedule,
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
    

# ============================================================
# HEALTH / NURSE
# ============================================================

@admin.register(HealthVisit)
class HealthVisitAdmin(admin.ModelAdmin):
    list_display = ('student', 'visit_date', 'visit_type', 'outcome', 'school', 'attended_by')
    list_filter = ('visit_type', 'outcome', 'school', 'visit_date')
    search_fields = ('student__first_name', 'student__last_name', 'symptoms', 'diagnosis')
    date_hierarchy = 'visit_date'


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'reorder_level', 'expiry_date', 'school', 'is_active')
    list_filter = ('category', 'school', 'is_active')
    search_fields = ('name', 'supplier')


@admin.register(MedicineLog)
class MedicineLogAdmin(admin.ModelAdmin):
    list_display = ('medicine', 'action', 'quantity', 'balance_after', 'recorded_by', 'created_at')
    list_filter = ('action', 'school')
    search_fields = ('medicine__name', 'reason')
    

# ============================================================
# KITCHEN / CHEF
# ============================================================

@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ('name', 'meal_type', 'served_time', 'cost_per_head', 'school', 'is_active')
    list_filter = ('meal_type', 'school', 'is_active')
    search_fields = ('name',)


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ('date', 'meal', 'head_count', 'school', 'created_by')
    list_filter = ('school', 'date')
    date_hierarchy = 'date'


@admin.register(KitchenStock)
class KitchenStockAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'unit_cost', 'school', 'is_active')
    list_filter = ('category', 'school', 'is_active')
    search_fields = ('name', 'supplier')


@admin.register(KitchenLog)
class KitchenLogAdmin(admin.ModelAdmin):
    list_display = ('stock_item', 'action', 'quantity', 'balance_after', 'recorded_by', 'created_at')
    list_filter = ('action', 'school')
    search_fields = ('stock_item__name', 'reason')


@admin.register(MealServing)
class MealServingAdmin(admin.ModelAdmin):
    list_display = ('meal_plan', 'students_served', 'staff_served', 'wastage_plates', 'served_by', 'served_at')
    list_filter = ('school',)
    

# ============================================================
# LABORATORY
# ============================================================

@admin.register(LabEquipment)
class LabEquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'working_quantity', 'condition', 'school', 'is_active')
    list_filter = ('category', 'condition', 'school', 'is_active')
    search_fields = ('name', 'location', 'supplier')


@admin.register(LabIncident)
class LabIncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_type', 'incident_date', 'severity', 'equipment', 'school', 'resolved')
    list_filter = ('incident_type', 'severity', 'school', 'resolved')
    search_fields = ('description', 'class_involved')
    date_hierarchy = 'incident_date'


@admin.register(PracticalSchedule)
class PracticalScheduleAdmin(admin.ModelAdmin):
    list_display = ('title', 'class_level', 'scheduled_date', 'start_time', 'teacher', 'school', 'is_completed')
    list_filter = ('school', 'class_level', 'is_completed', 'scheduled_date')
    search_fields = ('title', 'subject', 'teacher')
    date_hierarchy = 'scheduled_date'