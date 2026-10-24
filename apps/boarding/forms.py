"""
Boarding forms.

All querysets are scoped to the current school. Views pass `school` via the
`school` kwarg so no cross-tenant data ever appears in a dropdown.
"""
from django import forms

from .models import BoardingDormitory, BoardingBed, BoardingAssignment


class DormitoryForm(forms.ModelForm):
    """Create / edit a dormitory."""

    class Meta:
        model = BoardingDormitory
        fields = ['name', 'code', 'gender', 'capacity', 'house_master', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Kilimanjaro House'}),
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. KIL'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'house_master': forms.Select(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['house_master'].required = False
        self.fields['house_master'].empty_label = '— Unassigned —'
        if school is not None:
            self.fields['house_master'].queryset = (
                school.users
                .filter(role='boarding_master', is_active=True)
                .order_by('first_name', 'last_name')
            )
        else:
            self.fields['house_master'].queryset = self.fields['house_master'].queryset.none()


class BedForm(forms.ModelForm):
    """Create / edit a single bed."""

    class Meta:
        model = BoardingBed
        fields = ['dormitory', 'bed_number', 'notes']
        widgets = {
            'dormitory': forms.Select(attrs={'class': 'form-input'}),
            'bed_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. A-01'}),
            'notes': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Optional'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school is not None:
            self.fields['dormitory'].queryset = (
                BoardingDormitory.objects
                .filter(school=school, is_active=True)
                .order_by('name')
            )
        else:
            self.fields['dormitory'].queryset = BoardingDormitory.objects.none()


class BedBulkForm(forms.Form):
    """Generate many beds in one submission, e.g. A-01 .. A-30."""

    dormitory = forms.ModelChoiceField(
        queryset=BoardingDormitory.objects.none(),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    prefix = forms.CharField(
        max_length=10,
        initial='A-',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'A-'}),
        help_text="Prepended to each bed number.",
    )
    start = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
        help_text="First number in the sequence.",
    )
    count = forms.IntegerField(
        min_value=1,
        max_value=200,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 200}),
        help_text="How many beds to generate (1–200).",
    )
    width = forms.IntegerField(
        min_value=1,
        max_value=4,
        initial=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 4}),
        help_text="Zero-padding width, e.g. 2 gives A-01, A-02…",
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school is not None:
            self.fields['dormitory'].queryset = (
                BoardingDormitory.objects
                .filter(school=school, is_active=True)
                .order_by('name')
            )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('start') is not None and cleaned.get('count') is not None:
            end = cleaned['start'] + cleaned['count'] - 1
            if end > 9999:
                raise forms.ValidationError("Sequence too large. Reduce count or start.")
        return cleaned


class AssignmentForm(forms.ModelForm):
    """Create a new assignment for a boarding student."""

    class Meta:
        model = BoardingAssignment
        fields = ['student', 'dormitory', 'bed', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-input'}),
            'dormitory': forms.Select(attrs={'class': 'form-input'}),
            'bed': forms.Select(attrs={'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school is None:
            self.fields['student'].queryset = self.fields['student'].queryset.none()
            self.fields['dormitory'].queryset = BoardingDormitory.objects.none()
            self.fields['bed'].queryset = BoardingBed.objects.none()
            return

        # Boarding students in this school who do NOT have an active assignment.
        from apps.students.models import Student
        assigned_ids = (
            BoardingAssignment.objects
            .filter(status=BoardingAssignment.Status.ACTIVE)
            .values_list('student_id', flat=True)
        )
        self.fields['student'].queryset = (
            Student.objects
            .filter(school=school, is_boarding=True, is_active=True)
            .exclude(pk__in=assigned_ids)
            .order_by('admission_number')
        )

        self.fields['dormitory'].queryset = (
            BoardingDormitory.objects.filter(school=school, is_active=True).order_by('name')
        )
        self.fields['bed'].queryset = (
            BoardingBed.objects
            .filter(dormitory__school=school, is_occupied=False)
            .select_related('dormitory')
            .order_by('dormitory__name', 'bed_number')
        )

    def clean(self):
        cleaned = super().clean()
        dorm = cleaned.get('dormitory')
        bed = cleaned.get('bed')
        if bed and dorm and bed.dormitory_id != dorm.id:
            raise forms.ValidationError("Selected bed does not belong to the selected dormitory.")
        if bed and bed.is_occupied:
            raise forms.ValidationError("That bed is already occupied.")
        return cleaned


class AssignmentCheckoutForm(forms.Form):
    """Reason text for checking out an active assignment."""

    reason = forms.CharField(
        label="Check-out reason",
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 3,
            'placeholder': 'e.g. Transferred to day scholar, parent request, end of term…',
        }),
    )