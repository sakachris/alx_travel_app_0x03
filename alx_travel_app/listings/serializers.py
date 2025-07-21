# listings/serializers.py
from rest_framework import serializers
from .models import Property, Booking, Payment, User
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueValidator

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'phone_number', 'role')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data.get('phone_number'),
            role=validated_data.get('role', 'guest')
        )
        return user

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