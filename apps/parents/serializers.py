from rest_framework import serializers
from .models import Parent
from apps.students.serializers import StudentSerializer


class ParentSerializer(serializers.ModelSerializer):
    students_detail = StudentSerializer(source='students', many=True, read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Parent
        fields = ['id', 'user', 'email', 'occupation', 'relationship',
                  'students', 'students_detail']