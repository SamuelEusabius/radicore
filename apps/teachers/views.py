from rest_framework import viewsets
from .models import Teacher
from .serializers import TeacherSerializer
from apps.accounts.permissions import IsSchoolAdmin


class TeacherViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = Teacher.objects.select_related('user', 'school')
        if user.is_super_admin:
            return qs
        return qs.filter(school=user.school)

    def perform_create(self, serializer):
        serializer.save(school=self.request.user.school)