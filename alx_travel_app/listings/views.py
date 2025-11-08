# listings/views.py

import logging
import time
from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Property, Booking, Payment, Review
from .serializers import InitiatePaymentSerializer, PropertySerializer, BookingSerializer, RegisterSerializer, ReviewSerializer
from .chapa import initiate_payment, verify_payment
from .tasks import send_payment_confirmation_email, send_booking_confirmation_email
from rest_framework import viewsets
from rest_framework import status
from django.core.mail import send_mail
from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from .permissions import IsOwnerOrReadOnly, IsBookingOwner, IsHostOwnerOrReadOnly
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


logger = logging.getLogger(__name__)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Include user info in token
        token['email'] = user.email
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include user info in the response
        data.update({
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
        })
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



class PropertyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Property instances.

    Provides standard CRUD actions (list, retrieve, create, update, delete)
    for the Property model.
    """

    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    permission_classes = [IsHostOwnerOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)

def get_guest_user():
    guest, created = User.objects.get_or_create(
        email="guest@system.local",
        defaults={
            "first_name": "Guest",
            "last_name": "User",
            "password": "guestpassword123"
        }
    )
    return guest


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    # permission_classes = [IsAuthenticated, IsBookingOwner]
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Booking.objects.filter(user=user)
        # Guests shouldn’t see all bookings, return empty queryset
        return Booking.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            user = get_guest_user()
        serializer.save(user=user)

    # def get_queryset(self):
    #     # Only show bookings owned by the authenticated user
    #     return Booking.objects.filter(user=self.request.user)

    # def perform_create(self, serializer):
    #     # Automatically assign the booking to the current user
    #     booking = serializer.save(user=self.request.user)

        # Trigger async email task
        # send_booking_confirmation_email.delay(
        #     to_email=booking.user.email,
        #     property_name=booking.property.name,
        #     start_date=str(booking.start_date),
        #     end_date=str(booking.end_date),
        #     total_price=str(booking.total_price)
        # )

class InitiatePaymentView(APIView):
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            print("❌ Invalid data:", serializer.errors)
            return Response(serializer.errors, status=400)

        booking_id = serializer.validated_data["booking_id"]
        print(f"🔰 Initiating payment for booking_id: {booking_id}")

        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            print("❌ Booking not found")
            return Response({"error": "Booking not found"}, status=404)

        amount = str(booking.total_price)
        tx_ref = f"chapa-{booking.booking_id}"
        email = booking.user.email
        first_name = booking.user.first_name
        last_name = booking.user.last_name

        # Use localhost test URLs or settings with fallback
        base_callback_url = getattr(settings, "CHAPA_CALLBACK_URL", "http://127.0.0.1:8000/api/payment/verify/")
        base_return_url = getattr(settings, "CHAPA_RETURN_URL", "http://127.0.0.1:8000/api/payment/success/")
        return_url = f"{base_return_url}?tx_ref={tx_ref}" 
        callback_url = f"{base_callback_url}?tx_ref={tx_ref}"

        chapa_data = {
            "amount": amount,
            "currency": settings.DEFAULT_CURRENCY,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization[title]": "Property Booking",
        }

        print(f"📤 Sending payment data to Chapa: {chapa_data}")
        chapa_response = initiate_payment(chapa_data)
        print(f"📥 Chapa response: {chapa_response}")

        if chapa_response.get("status") == "success":
            Payment.objects.create(
                booking=booking,
                amount=amount,
                transaction_id=tx_ref,
                status="Pending",
            )
            print("✅ Payment record created, redirecting user")
            return Response({
                "checkout_url": chapa_response["data"]["checkout_url"],
                "transaction_id": tx_ref
            }, status=200)
        else:
            print("❌ Chapa failed to initiate payment")
            return Response({
                "error": "Payment initiation failed",
                "details": chapa_response
            }, status=400)


class VerifyPaymentView(APIView):
    def get(self, request):
        query = request.query_params
        print("🔁 Chapa returned with query params:", dict(query))

        tx_ref = query.get("tx_ref") or query.get("trx_ref") or query.get("transaction_id")
        if not tx_ref:
            print("❌ Missing tx_ref")
            return Response({"error": "Missing transaction_id or tx_ref"}, status=400)

        time.sleep(2)  # Give Chapa time to finalize the transaction

        try:
            payment = Payment.objects.get(transaction_id=tx_ref)
            print(f"✅ Found payment: {payment}")
        except Payment.DoesNotExist:
            print(f"⚠️ Payment not found for {tx_ref}, trying to create...")
            booking_id = tx_ref.replace("chapa-", "")
            try:
                booking = Booking.objects.get(booking_id=booking_id)
                payment = Payment.objects.create(
                    booking=booking,
                    amount=booking.total_price,
                    transaction_id=tx_ref,
                    status="Pending"
                )
                print("✅ Fallback payment record created")
            except Booking.DoesNotExist:
                print("❌ Booking not found for tx_ref")
                return Response({"error": f"No booking found for tx_ref {tx_ref}"}, status=404)

        chapa_response = verify_payment(tx_ref)
        print(f"🧾 Chapa verify response: {chapa_response}")

        status_chapa = chapa_response.get("data", {}).get("status")

        if status_chapa == "success":
            payment.status = "Completed"
            payment.save()
            print("✅ Payment marked as Completed")

            try:
                send_payment_confirmation_email.delay(
                    to_email=payment.booking.user.email,
                    property_name=payment.booking.property.name,
                    start_date=str(payment.booking.start_date),
                    end_date=str(payment.booking.end_date),
                    amount=payment.amount
                )
                print("📧 Email task dispatched")
            except Exception as e:
                print(f"⚠️ Failed to send email: {e}")

            return Response({
                "message": "✅ Payment verified and booking confirmed.",
                "booking": {
                    "property": payment.booking.property.name,
                    "start_date": str(payment.booking.start_date),
                    "end_date": str(payment.booking.end_date),
                    "amount": str(payment.amount)
                },
                "email_sent": True
            }, status=200)
        else:
            payment.status = "Failed"
            payment.save()
            print("❌ Payment verification failed")
            return Response({"message": "Payment failed"}, status=400)
            

class SuccessPaymentView(APIView):
    def get(self, request):
        tx_ref = request.query_params.get("tx_ref")

        if not tx_ref:
            return Response({"error": "Missing transaction reference (tx_ref)."}, status=400)

        try:
            payment = Payment.objects.select_related("booking__property", "booking__user").get(transaction_id=tx_ref)
        except Payment.DoesNotExist:
            return Response({"error": f"No payment found with transaction ID: {tx_ref}"}, status=404)

        # 🔁 Try verify again if still pending
        if payment.status == "Pending":
            print(f"🔁 Re-verifying payment {tx_ref} as it's still pending.")
            chapa_response = verify_payment(tx_ref)
            status_chapa = chapa_response.get("data", {}).get("status")
            if status_chapa == "success":
                payment.status = "Completed"
                payment.save()
                try:
                    send_payment_confirmation_email.delay(
                        to_email=payment.booking.user.email,
                        property_name=payment.booking.property.name,
                        start_date=str(payment.booking.start_date),
                        end_date=str(payment.booking.end_date),
                        amount=payment.amount
                    )
                except Exception as e:
                    print(f"⚠️ Failed to send email from return_url: {e}")

        if payment.status != "Completed":
            return Response({
                "message": "Payment received but not yet verified. Please check again shortly.",
                "status": payment.status
            }, status=202)

        booking = payment.booking
        return Response({
            "message": "🎉 Payment Successful and Booking Confirmed!",
            "payment": {
                "transaction_id": tx_ref,
                "amount": str(payment.amount),
                "status": payment.status
            },
            "booking": {
                "property": booking.property.name,
                "start_date": str(booking.start_date),
                "end_date": str(booking.end_date),
                "user": booking.user.email
            }
        }, status=status.HTTP_200_OK)


class PropertyReviewListView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        property_id = self.kwargs["property_id"]
        return Review.objects.filter(property_id=property_id).order_by("-created_at")


class ReviewCreateView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        guest_user = get_guest_user()  # Assign guest user
        serializer.save(user=guest_user)
