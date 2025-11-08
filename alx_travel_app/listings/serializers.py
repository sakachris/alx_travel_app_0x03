# listings/serializers.py
from rest_framework import serializers
from .models import Property, Booking, Payment, User, Review
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

# class PropertySerializer(serializers.ModelSerializer):
#     # host = serializers.PrimaryKeyRelatedField(
#     #     queryset=User.objects.filter(role='host')
#     # )
#     host = serializers.ReadOnlyField(source='user.id')
#     class Meta:
#         model = Property
#         fields = '__all__'
#         read_only_fields = ['host']
class PropertySerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            "property_id",
            "name",
            "address",
            "rating",
            "category",
            "pricepernight",
            "offers",
            "image",
            "discount",
        ]

    def get_address(self, obj):
        return {
            "state": obj.state,
            "city": obj.city,
            "country": obj.country,
        }

    def get_offers(self, obj):
        return {
            "bed": str(obj.bed),
            "shower": str(obj.shower),
            "occupants": obj.occupants,
        }

# class BookingSerializer(serializers.ModelSerializer):
#     user = serializers.ReadOnlyField(source='user.id')

#     class Meta:
#         model = Booking
#         fields = '__all__'
#         read_only_fields = ['user', 'total_price', 'status']

class BookingSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.user_id')
    property_name = serializers.ReadOnlyField(source='property.name')
    property_price = serializers.ReadOnlyField(source='property.pricepernight')

    class Meta:
        model = Booking
        fields = [
            'booking_id',
            'property',
            'property_name',
            'property_price',
            'user',
            'start_date',
            'end_date',
            'total_price',
            'status',
            'created_at',
        ]
        read_only_fields = ['user', 'total_price', 'status', 'created_at']


# class BookingSerializer(serializers.ModelSerializer):
#     user = serializers.PrimaryKeyRelatedField(
#         queryset=User.objects.filter(role='guest')
#     )
#     class Meta:
#         model = Booking
#         fields = '__all__'
#         read_only_fields = ['total_price', 'status']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

class InitiatePaymentSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()


class ReviewSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.first_name", read_only=True)
    avatar = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "review_id",
            "property",
            "name",
            "avatar",
            "rating",
            "comment",
            "date",
        ]

    def get_avatar(self, obj):
        if hasattr(obj.user, "avatar") and obj.user.avatar:
            return obj.user.avatar.url
        return "/static/defaults/avatar.png"

    def get_date(self, obj):
        return obj.created_at.strftime("%B %Y")
