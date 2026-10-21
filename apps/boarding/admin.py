from django.contrib import admin

from .models import BoardingDormitory, BoardingBed, BoardingAssignment


class BedInline(admin.TabularInline):
    model = BoardingBed
    extra = 0
    fields = ('bed_number', 'is_occupied', 'notes')
    readonly_fields = ('is_occupied',)


@admin.register(BoardingDormitory)
class BoardingDormitoryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'school', 'gender', 'house_master',
        'bed_count_display', 'occupied_display', 'is_active',
    )
    list_filter = ('school', 'gender', 'is_active')
    search_fields = ('name', 'code')
    inlines = [BedInline]

    def bed_count_display(self, obj):
        return obj.bed_count
    bed_count_display.short_description = 'Beds'

    def occupied_display(self, obj):
        return f"{obj.occupied_count} / {obj.bed_count} ({obj.occupancy_percent}%)"
    occupied_display.short_description = 'Occupancy'


@admin.register(BoardingBed)
class BoardingBedAdmin(admin.ModelAdmin):
    list_display = ('dormitory', 'bed_number', 'is_occupied', 'notes')
    list_filter = ('dormitory', 'is_occupied')
    search_fields = ('bed_number',)


@admin.register(BoardingAssignment)
class BoardingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'dormitory', 'bed', 'status',
        'assigned_at', 'assigned_by',
    )
    list_filter = ('status', 'dormitory', 'dormitory__school')
    search_fields = (
        'student__first_name', 'student__last_name',
        'student__admission_number',
    )
    readonly_fields = ('created_at', 'updated_at')

    def school_filter(self, obj):
        return obj.dormitory.school
    school_filter.short_description = 'School'