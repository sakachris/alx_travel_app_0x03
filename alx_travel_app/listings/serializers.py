# listings/serializers.py
from rest_framework import serializers
from .models import Property, Booking, Payment, User

class PropertySerializer(serializers.ModelSerializer):
    host = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='host')
    )
    class Meta:
        model = Property
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='guest')
    )
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['total_price', 'status']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class InitiatePaymentSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()