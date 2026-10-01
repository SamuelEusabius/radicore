from django import forms
from .models import Timetable, ClassLevel, Subject


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['class_level', 'subject', 'teacher', 'day_of_week', 'start_time', 'end_time']
        widgets = {
            'class_level': forms.Select(attrs={'class': 'w-full border p-2 rounded'}),
            'subject': forms.Select(attrs={'class': 'w-full border p-2 rounded'}),
            'teacher': forms.Select(attrs={'class': 'w-full border p-2 rounded'}),
            'day_of_week': forms.Select(attrs={'class': 'w-full border p-2 rounded'}),
            'start_time': forms.TimeInput(attrs={'class': 'w-full border p-2 rounded', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'w-full border p-2 rounded', 'type': 'time'}),
        }
        labels = {
            'class_level': 'Class',
            'day_of_week': 'Day',
            'start_time': 'Start Time',
            'end_time': 'End Time',
        }