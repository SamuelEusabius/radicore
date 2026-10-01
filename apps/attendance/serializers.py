from rest_framework import serializers
from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.__str__', read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['recorded_by']