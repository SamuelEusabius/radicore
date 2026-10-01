from rest_framework import serializers
from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = ['school']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"