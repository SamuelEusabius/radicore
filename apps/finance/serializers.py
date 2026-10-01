from rest_framework import serializers
from .models import FeeStructure, Invoice, Payment


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = '__all__'
        read_only_fields = ['school']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['paid_at']


class InvoiceSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True, read_only=True)
    balance = serializers.ReadOnlyField()
    student_name = serializers.CharField(source='student.__str__', read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['amount_paid', 'status', 'created_at']