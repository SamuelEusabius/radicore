from django import forms
from django.utils import timezone

from .models import Visitor, GatePass, Incident, LostItem, SecurityShift


class VisitorCheckInForm(forms.ModelForm):
    """CSO registers a visitor at the gate."""

    class Meta:
        model = Visitor
        fields = [
            'full_name', 'phone', 'id_type', 'id_number', 'organisation',
            'vehicle_plate', 'badge_number',
            'purpose', 'purpose_note',
            'visit_type',
            'host_user', 'host_name', 'host_role',
        ]
        widgets = {
            'purpose_note': forms.Textarea(attrs={'rows': 2}),
            'full_name':    forms.TextInput(attrs={'placeholder': 'Full name'}),
            'host_name':    forms.TextInput(attrs={'placeholder': "Host (if not a system user)"}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            # Limit host choices to staff at this school
            from apps.accounts.models import User
            self.fields['host_user'].queryset = User.objects.filter(
                school=school
            ).exclude(role__in=('student', 'parent')).order_by('first_name', 'last_name')
            self.fields['host_user'].required = False
        self.fields['host_name'].required = False
        self.fields['host_user'].label = 'Host (staff member)'
        self.fields['host_name'].label = 'Host (free text)'

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('host_user') and not cleaned.get('host_name'):
            raise forms.ValidationError(
                "Specify who the visitor is coming to see — "
                "either pick a staff member or type a name."
            )
        return cleaned


class GatePassIssueForm(forms.ModelForm):
    class Meta:
        model = GatePass
        fields = ['pass_type', 'destination', 'valid_from', 'valid_until', 'notes']
        widgets = {
            'valid_from':  forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes':       forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['valid_until'].required = False


class OfficialPassIssueForm(forms.ModelForm):
    class Meta:
        model = GatePass
        fields = ['destination', 'valid_from', 'valid_until', 'notes']
        widgets = {
            'valid_from':  forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valid_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes':       forms.Textarea(attrs={'rows': 3}),
        }


class SignOfficialPassForm(forms.ModelForm):
    class Meta:
        model = GatePass
        fields = ['signed_by_name', 'signature_image', 'notes']


class VisitorCheckOutForm(forms.Form):
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes'}),
    )


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = [
            'title', 'category', 'severity', 'status', 'location',
            'occurred_at', 'description', 'action_taken', 'resolution',
            'involved_student',
        ]
        widgets = {
            'occurred_at':  forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description':  forms.Textarea(attrs={'rows': 4}),
            'action_taken': forms.Textarea(attrs={'rows': 3}),
            'resolution':   forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['involved_student'].queryset = (
                Student.objects.filter(school=school).order_by('first_name', 'last_name')
            )
        self.fields['involved_student'].required = False


class LostItemForm(forms.ModelForm):
    class Meta:
        model = LostItem
        fields = ['name', 'description', 'found_at', 'found_location', 'status']
        widgets = {
            'found_at':    forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ClaimLostItemForm(forms.ModelForm):
    class Meta:
        model = LostItem
        fields = ['claimed_by_name', 'claimed_by_phone']

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.status = LostItem.ItemStatus.CLAIMED
        obj.claimed_at = timezone.now()
        if commit:
            obj.save()
        return obj


class SecurityShiftForm(forms.ModelForm):
    class Meta:
        model = SecurityShift
        fields = [
            'guard', 'shift_date', 'shift_type', 'post',
            'check_in', 'check_out', 'notes',
        ]
        widgets = {
            'shift_date': forms.DateInput(attrs={'type': 'date'}),
            'check_in':   forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'check_out':  forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes':      forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from apps.accounts.models import User
            self.fields['guard'].queryset = User.objects.filter(
                school=school
            ).order_by('first_name', 'last_name')


# Import Student at module level for the IncidentForm queryset
from apps.students.models import Student  # noqa: E402