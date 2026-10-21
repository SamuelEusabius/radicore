from django.contrib import admin

from .models import County, Constituency, Ward


class ConstituencyInline(admin.TabularInline):
    model = Constituency
    extra = 0
    fields = ('code', 'name')
    readonly_fields = ('code',)


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'constituency_count', 'ward_count')
    search_fields = ('code', 'name')
    list_filter = ()
    inlines = []

    def constituency_count(self, obj):
        return obj.constituencies.count()
    constituency_count.short_description = 'Constituencies'

    def ward_count(self, obj):
        return Ward.objects.filter(constituency__county=obj).count()
    ward_count.short_description = 'Wards'


@admin.register(Constituency)
class ConstituencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'county', 'ward_count')
    list_filter = ('county',)
    search_fields = ('code', 'name')

    def ward_count(self, obj):
        return obj.wards.count()
    ward_count.short_description = 'Wards'


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'constituency')
    list_filter = ('constituency__county', 'constituency')
    search_fields = ('code', 'name')