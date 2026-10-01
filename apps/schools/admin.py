from django.contrib import admin
from .models import School, SubscriptionPlan, BoardMember
from .models import School, SubscriptionPlan, SchoolSubscription, SchoolModule


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'plan', 'school_type', 'gender', 'level', 'is_active', 'created_at']
    list_filter = ['is_active', 'plan', 'school_type', 'gender', 'level', 'county']
    search_fields = ['name', 'nemis_code', 'county', 'principal_name']
    prepopulated_fields = {'slug': ('name',)}
@admin.register(SchoolModule)
class SchoolModuleAdmin(admin.ModelAdmin):
    list_display = (
        'school', 'module', 'is_enabled',
        'enabled_at', 'enabled_by',
        'disabled_at', 'disabled_by',
    )
    list_filter = ('module', 'is_enabled', 'school')
    search_fields = ('school__name',)
    list_editable = ('is_enabled',)
    ordering = ('school', 'module')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50


@admin.register(SubscriptionPlan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'min_students', 'max_students',
        'monthly_price', 'term_price',
        'contract_1y_price', 'contract_2y_price',
        'order', 'is_active',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('order', 'min_students')
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'code', 'order', 'is_active')
        }),
        ('Student Range', {
            'fields': ('min_students', 'max_students', 'max_teachers')
        }),
        ('Pricing (KES)', {
            'fields': (
                'monthly_price',
                'term_price',
                'contract_1y_price',
                'contract_2y_price',
            )
        }),
        ('Features', {
            'fields': ('features',),
            'description': 'Enter features as a JSON list: ["Feature 1", "Feature 2"]'
        }),
    )

@admin.register(BoardMember)
class BoardMemberAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'role', 'school', 'id_number', 'phone']
    list_filter = ['role', 'school']
    search_fields = ['full_name', 'id_number', 'phone']