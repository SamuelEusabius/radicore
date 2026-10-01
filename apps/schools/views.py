from rest_framework import viewsets
from .models import School, SubscriptionPlan
from .serializers import SchoolSerializer, SubscriptionPlanSerializer
from apps.accounts.permissions import IsSuperAdmin


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperAdmin]
    lookup_field = 'slug'


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsSuperAdmin]