from rest_framework import viewsets
from .models import Parent
from .serializers import ParentSerializer
from apps.accounts.permissions import IsSchoolAdmin


class ParentViewSet(viewsets.ModelViewSet):
    serializer_class = ParentSerializer
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = Parent.objects.select_related('user').prefetch_related('students')
        if user.is_super_admin:
            return qs
        return qs.filter(user__school=user.school)