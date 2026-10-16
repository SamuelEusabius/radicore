from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Appointment, Correspondence, Notice, AdmissionApplication


# Common widget class helper
def _c(cls='input'):
    return {'class': cls}


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'requester_name', 'requester_phone', 'requester_email', 'requester_org',
            'host_user', 'host_name',
            'subject', 'purpose', 'location',
            'scheduled_date', 'scheduled_time', 'duration_minutes',
            'status', 'notes',
        ]
        widgets = {
            'requester_name':  forms.TextInput(attrs={'class': 'input', 'placeholder': 'Full name'}),
            'requester_phone': forms.TextInput(attrs={'class': 'input', 'placeholder': '07XX XXX XXX'}),
            'requester_email': forms.EmailInput(attrs={'class': 'input'}),
            'requester_org':   forms.TextInput(attrs={'class': 'input'}),
            'host_user':       forms.Select(attrs={'class': 'select'}),
            'host_name':       forms.TextInput(attrs={'class': 'input'}),
            'subject':         forms.TextInput(attrs={'class': 'input'}),
            'purpose':         forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'location':        forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Boardroom'}),
            'scheduled_date':  forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'scheduled_time':  forms.TimeInput(attrs={'class': 'input', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'input', 'min': 15, 'step': 15}),
            'status':          forms.Select(attrs={'class': 'select'}),
            'notes':           forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from apps.accounts.models import User
            self.fields['host_user'].queryset = (
                User.objects.filter(school=school)
                .exclude(role__in=('student', 'parent'))
                .order_by('first_name', 'last_name')
            )
        self.fields['host_user'].required = False
        self.fields['host_name'].required = False
        if not self.instance.pk:
            self.fields['scheduled_date'].initial = timezone.localdate()
            self.fields['scheduled_time'].initial = '09:00'

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('host_user') and not cleaned.get('host_name'):
            raise forms.ValidationError("Pick a staff host or type a name.")
        return cleaned


class AppointmentCompleteForm(forms.ModelForm):
    """Used when marking an appointment complete + uploading minutes."""
    class Meta:
        model = Appointment
        fields = ['notes', 'minutes', 'status']
        widgets = {
            'notes':   forms.Textarea(attrs={'class': 'textarea', 'rows': 4}),
            'minutes': forms.ClearableFileInput(attrs={'class': 'input'}),
            'status':  forms.Select(attrs={'class': 'select'}),
        }


class CorrespondenceForm(forms.ModelForm):
    class Meta:
        model = Correspondence
        fields = [
            'direction',
            'correspondent_name', 'correspondent_org',
            'correspondent_phone', 'correspondent_email',
            'subject', 'summary', 'document',
            'priority', 'status',
            'date_received', 'date_dispatched',
            'assigned_to', 'action_taken', 'notes',
        ]
        widgets = {
            'direction':          forms.Select(attrs={'class': 'select'}),
            'correspondent_name': forms.TextInput(attrs={'class': 'input'}),
            'correspondent_org':  forms.TextInput(attrs={'class': 'input'}),
            'correspondent_phone':forms.TextInput(attrs={'class': 'input'}),
            'correspondent_email':forms.EmailInput(attrs={'class': 'input'}),
            'subject':            forms.TextInput(attrs={'class': 'input'}),
            'summary':            forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'document':           forms.ClearableFileInput(attrs={'class': 'input'}),
            'priority':           forms.Select(attrs={'class': 'select'}),
            'status':             forms.Select(attrs={'class': 'select'}),
            'date_received':      forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'date_dispatched':    forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'assigned_to':        forms.Select(attrs={'class': 'select'}),
            'action_taken':       forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'notes':              forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            from apps.accounts.models import User
            self.fields['assigned_to'].queryset = (
                User.objects.filter(school=school)
                .exclude(role__in=('student', 'parent'))
                .order_by('first_name', 'last_name')
            )
        self.fields['assigned_to'].required = False
        self.fields['date_received'].required = False
        self.fields['date_dispatched'].required = False


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = [
            'title', 'body', 'audience', 'priority',
            'attachment', 'is_published', 'expires_at',
        ]
        widgets = {
            'title':    forms.TextInput(attrs={'class': 'input'}),
            'body':     forms.Textarea(attrs={'class': 'textarea', 'rows': 6}),
            'audience': forms.Select(attrs={'class': 'select'}),
            'priority': forms.Select(attrs={'class': 'select'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'checkbox'}),
            'expires_at': forms.DateTimeInput(attrs={'class': 'input', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['expires_at'].required = False


class AdmissionApplicationForm(forms.ModelForm):
    class Meta:
        model = AdmissionApplication
        fields = [
            'first_name', 'middle_name', 'last_name',
            'gender', 'date_of_birth',
            'applying_for_class', 'previous_school',
            'guardian_name', 'guardian_phone', 'guardian_email',
            'guardian_id_number', 'relationship',
            'birth_certificate', 'report_card', 'other_document',
            'status', 'notes',
        ]
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'input'}),
            'middle_name': forms.TextInput(attrs={'class': 'input'}),
            'last_name':   forms.TextInput(attrs={'class': 'input'}),
            'gender':      forms.Select(attrs={'class': 'select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'applying_for_class': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Grade 5 East'}),
            'previous_school': forms.TextInput(attrs={'class': 'input'}),
            'guardian_name':   forms.TextInput(attrs={'class': 'input'}),
            'guardian_phone':  forms.TextInput(attrs={'class': 'input'}),
            'guardian_email':  forms.EmailInput(attrs={'class': 'input'}),
            'guardian_id_number': forms.TextInput(attrs={'class': 'input'}),
            'relationship':    forms.TextInput(attrs={'class': 'input', 'placeholder': 'Parent / Guardian'}),
            'birth_certificate': forms.ClearableFileInput(attrs={'class': 'input'}),
            'report_card':       forms.ClearableFileInput(attrs={'class': 'input'}),
            'other_document':    forms.ClearableFileInput(attrs={'class': 'input'}),
            'status':            forms.Select(attrs={'class': 'select'}),
            'notes':             forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date_of_birth'].required = False