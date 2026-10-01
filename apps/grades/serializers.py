from rest_framework import serializers
from .models import Exam, Grade


class ExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = '__all__'
        read_only_fields = ['school']


class GradeSerializer(serializers.ModelSerializer):
    percentage = serializers.ReadOnlyField()
    student_name = serializers.CharField(source='student.__str__', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = Grade
        fields = '__all__'