from rest_framework import viewsets
from .models import Attendance
from .serializers import AttendanceSerializer
from apps.accounts.permissions import IsTeacher
from django.utils import timezone


class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsTeacher]

    def get_queryset(self):
        user = self.request.user
        qs = Attendance.objects.select_related('student')
        if user.is_super_admin:
            return qs
        return qs.filter(student__school=user.school)

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)