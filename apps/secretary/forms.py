from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Appointment, Correspondence, Notice, AdmissionApplication


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
            'applying_for_class',
            'previous_school', 'previous_class',
            'previous_academic_results', 'leaving_certificate',
            'county_fk', 'constituency_fk', 'ward_fk',
            'sub_county', 'location', 'village',
            'birth_certificate_number',
            'birth_certificate_file', 'parent_id_file',
            'has_disability', 'disability_details',
            'disability_support_document',
            'has_medical_condition', 'medical_condition_details',
            'medical_report',
            'requires_medication', 'medication_notes',
            'guardian_name', 'guardian_phone', 'guardian_email',
            'parent_id_number', 'parent_occupation',
            'parent_county_fk', 'parent_constituency_fk',
            'parent_location', 'parent_village',
            'relationship',
            'second_parent_name', 'second_parent_phone',
            'second_parent_email', 'second_parent_id_number',
            'second_parent_occupation', 'second_parent_relationship',
            'is_boarding',
            'status', 'notes',
        ]
        widgets = {
            'first_name':  forms.TextInput(attrs={'class': 'input', 'placeholder': 'First name'}),
            'middle_name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Middle name (optional)'}),
            'last_name':   forms.TextInput(attrs={'class': 'input', 'placeholder': 'Last name'}),
            'gender':      forms.Select(attrs={'class': 'select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'input', 'type': 'date'}),
            'applying_for_class': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Grade 5 East'}),
            'previous_school': forms.TextInput(attrs={'class': 'input'}),
            'previous_class':  forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Grade 4'}),
            'previous_academic_results': forms.ClearableFileInput(attrs={'class': 'input'}),
            'leaving_certificate': forms.ClearableFileInput(attrs={'class': 'input'}),
            'county_fk':       forms.Select(attrs={'class': 'select', 'id': 'id_county_fk'}),
            'constituency_fk': forms.Select(attrs={'class': 'select', 'id': 'id_constituency_fk'}),
            'ward_fk':         forms.Select(attrs={'class': 'select', 'id': 'id_ward_fk'}),
            'sub_county':      forms.TextInput(attrs={'class': 'input'}),
            'location':        forms.TextInput(attrs={'class': 'input'}),
            'village':         forms.TextInput(attrs={'class': 'input'}),
            'birth_certificate_number': forms.TextInput(attrs={'class': 'input'}),
            'birth_certificate_file':   forms.ClearableFileInput(attrs={'class': 'input'}),
            'parent_id_file':           forms.ClearableFileInput(attrs={'class': 'input'}),
            'has_disability': forms.CheckboxInput(attrs={'class': 'checkbox'}),
            'disability_details': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'disability_support_document': forms.ClearableFileInput(attrs={'class': 'input'}),
            'has_medical_condition': forms.CheckboxInput(attrs={'class': 'checkbox'}),
            'medical_condition_details': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'medical_report': forms.ClearableFileInput(attrs={'class': 'input'}),
            'requires_medication': forms.CheckboxInput(attrs={'class': 'checkbox'}),
            'medication_notes': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
            'guardian_name':   forms.TextInput(attrs={'class': 'input'}),
            'guardian_phone':  forms.TextInput(attrs={'class': 'input'}),
            'guardian_email':  forms.EmailInput(attrs={'class': 'input'}),
            'parent_id_number': forms.TextInput(attrs={'class': 'input'}),
            'parent_occupation': forms.TextInput(attrs={'class': 'input'}),
            'parent_county_fk': forms.Select(attrs={'class': 'select', 'id': 'id_parent_county_fk'}),
            'parent_constituency_fk': forms.Select(attrs={'class': 'select', 'id': 'id_parent_constituency_fk'}),
            'parent_location':  forms.TextInput(attrs={'class': 'input'}),
            'parent_village':   forms.TextInput(attrs={'class': 'input'}),
            'relationship':     forms.TextInput(attrs={'class': 'input', 'placeholder': 'Parent / Guardian'}),
            'second_parent_name': forms.TextInput(attrs={'class': 'input'}),
            'second_parent_phone': forms.TextInput(attrs={'class': 'input'}),
            'second_parent_email': forms.EmailInput(attrs={'class': 'input'}),
            'second_parent_id_number': forms.TextInput(attrs={'class': 'input'}),
            'second_parent_occupation': forms.TextInput(attrs={'class': 'input'}),
            'second_parent_relationship': forms.TextInput(attrs={'class': 'input'}),
            'is_boarding': forms.CheckboxInput(attrs={'class': 'checkbox'}),
            'status': forms.Select(attrs={'class': 'select'}),
            'notes': forms.Textarea(attrs={'class': 'textarea', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from apps.locations.models import County, Constituency, Ward
        
        self.fields['county_fk'].queryset = County.objects.all().order_by('name')
        self.fields['parent_county_fk'].queryset = County.objects.all().order_by('name')

        if self.instance.pk:
            if self.instance.county_fk_id:
                self.fields['constituency_fk'].queryset = Constituency.objects.filter(
                    county_id=self.instance.county_fk_id
                ).order_by('name')
            else:
                self.fields['constituency_fk'].queryset = Constituency.objects.none()

            if self.instance.constituency_fk_id:
                self.fields['ward_fk'].queryset = Ward.objects.filter(
                    constituency_id=self.instance.constituency_fk_id
                ).order_by('name')
            else:
                self.fields['ward_fk'].queryset = Ward.objects.none()
        else:
            self.fields['constituency_fk'].queryset = Constituency.objects.none()
            self.fields['ward_fk'].queryset = Ward.objects.none()

        self.fields['county_fk'].required = False
        self.fields['constituency_fk'].required = False
        self.fields['ward_fk'].required = False
        self.fields['parent_county_fk'].required = False
        self.fields['parent_constituency_fk'].required = False

        self.fields['previous_academic_results'].required = False
        self.fields['leaving_certificate'].required = False
        self.fields['birth_certificate_file'].required = False
        self.fields['parent_id_file'].required = False
        self.fields['disability_support_document'].required = False
        self.fields['medical_report'].required = False

    def clean(self):
        cleaned = super().clean()
        
        if cleaned.get('county_fk') and not cleaned.get('constituency_fk'):
            self.add_error('constituency_fk', 'Please select a constituency for this county.')

        if cleaned.get('constituency_fk') and not cleaned.get('ward_fk'):
            self.add_error('ward_fk', 'Please select a ward for this constituency.')

        return cleaned