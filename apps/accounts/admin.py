from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from .models import User


class CustomUserCreationForm(forms.ModelForm):
    """Custom form to auto-populate school."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name',
                  'role', 'school', 'phone')

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    list_display = ['email', 'username', 'get_full_name', 'role', 'school', 'is_active']
    list_filter = ['role', 'school', 'is_active']
    search_fields = ['email', 'username', 'first_name', 'last_name']
    ordering = ['email']

    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'school', 'phone', 'avatar')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2',
                       'first_name', 'last_name', 'role', 'school', 'phone'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Pre-select role from URL query param."""
        form = super().get_form(request, obj, **kwargs)
        if not obj:
            role = request.GET.get('role')
            if role and 'role' in form.base_fields:
                form.base_fields['role'].initial = role
        return form

    def save_model(self, request, obj, form, change):
        """Auto-set school for school admins."""
        if not obj.school_id and request.user.role == 'principal':
            obj.school = request.user.school
        super().save_model(request, obj, form, change)