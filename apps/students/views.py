from rest_framework import viewsets
from .models import Student
from .serializers import StudentSerializer
from apps.accounts.permissions import IsSchoolAdmin


class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = Student.objects.select_related('school')
        if user.is_super_admin:
            return qs
        return qs.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)