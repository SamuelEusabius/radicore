from rest_framework import serializers
from .models import ClassLevel, Subject, Timetable


class ClassLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassLevel
        fields = '__all__'
        read_only_fields = ['school']


class SubjectSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.get_full_name', read_only=True)
    class Meta:
        model = Subject
        fields = '__all__'
        read_only_fields = ['school']


class TimetableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Timetable
        fields = '__all__'
        read_only_fields = ['school']