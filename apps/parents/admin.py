from django.contrib import admin
from .models import Parent


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['user', 'first_name', 'last_name', 'relationship', 'occupation', 'children_count']
    list_filter = ['relationship']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'first_name', 'last_name', 'id_number', 'phone']
    raw_id_fields = ['user']
    filter_horizontal = ['students']

    fieldsets = (
        ('Account', {
            'fields': ('user',)
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'id_number', 'occupation', 'phone', 'photo')
        }),
        ('Relationship', {
            'fields': ('relationship',)
        }),
        ('Linked Children', {
            'fields': ('students',),
            'description': 'Select the students this parent/guardian is responsible for.'
        }),
    )

    def children_count(self, obj):
        return obj.students.count()
    children_count.short_description = 'Children'