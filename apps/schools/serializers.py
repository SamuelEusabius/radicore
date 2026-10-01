from rest_framework import serializers
from .models import School, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'


class SchoolSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    class Meta:
        model = School
        fields = ['id', 'name', 'slug', 'logo', 'email', 'phone',
                  'address', 'county', 'plan', 'plan_name', 'is_active', 'created_at']
        read_only_fields = ['slug', 'created_at']