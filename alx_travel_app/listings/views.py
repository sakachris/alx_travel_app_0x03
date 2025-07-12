# listings/views.py
from rest_framework import viewsets
from .models import Property, Booking, Payment
from .serializers import PropertySerializer, BookingSerializer, PaymentSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .chapa import initiate_payment, verify_payment
from django.conf import settings
from django.core.mail import send_mail
from .tasks import send_email_task 
import time


class PropertyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Property instances.

    Provides standard CRUD actions (list, retrieve, create, update, delete)
    for the Property model.
    """

    queryset = Property.objects.all()
    serializer_class = PropertySerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def perform_create(self, serializer):
        booking = serializer.save()
        send_email_task.delay(booking.user.email)


class InitiatePaymentView(APIView):
    """
    Initiates a payment request to Chapa for a given booking.
    """
    def post(self, request):
        booking_id = request.data.get("booking_id")
        print(f"Initiating payment for booking_id: {booking_id}")

        try:
            booking = Booking.objects.get(booking_id=booking_id)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        amount = str(booking.total_price)
        tx_ref = f"chapa-{booking.booking_id}"
        email = booking.user.email
        first_name = booking.user.first_name
        last_name = booking.user.last_name

        # Return and callback URLs can be the same
        callback_url = "http://127.0.0.1:8000/api/payment/verify/"
        return_url = "http://127.0.0.1:8000/api/"

        chapa_data = {
            "amount": amount,
            "currency": "ETB",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": callback_url,
            "customization[title]": "Property Booking",
        }

        print(f"Sending payment data to Chapa: {chapa_data}")
        chapa_response = initiate_payment(chapa_data)
        print(f"Chapa Response: {chapa_response}")

        if chapa_response.get("status") == "success":
            Payment.objects.create(
                booking=booking,
                amount=amount,
                transaction_id=tx_ref,
                status="Pending",
            )
            return Response({
                "checkout_url": chapa_response["data"]["checkout_url"],
                "transaction_id": tx_ref
            }, status=200)
        else:
            return Response({"error": "Payment initiation failed", "details": chapa_response}, status=400)


class VerifyPaymentView(APIView):
    """
    Verifies the payment status with Chapa and updates the Payment model.
    """
    def get(self, request):
        query = request.query_params
        print("Received Chapa verify callback with query params:", dict(query))

        tx_ref = query.get("trx_ref") or query.get("transaction_id")
        if not tx_ref:
            return Response({"error": "Missing transaction_id or trx_ref"}, status=400)

        # Sleep to avoid race condition (payment not saved yet)
        time.sleep(2)

        # Try to fetch existing payment
        try:
            payment = Payment.objects.get(transaction_id=tx_ref)
            print(f"Found payment: {payment}")
        except Payment.DoesNotExist:
            print(f"Payment with tx_ref {tx_ref} not found. Attempting to recover from booking...")
            try:
                booking_id = tx_ref.replace("chapa-", "")
                booking = Booking.objects.get(booking_id=booking_id)
                payment = Payment.objects.create(
                    booking=booking,
                    amount=booking.total_price,
                    transaction_id=tx_ref,
                    status="Pending"
                )
                print(f"Created fallback payment record for booking: {booking_id}")
            except Booking.DoesNotExist:
                return Response({"error": "No booking found for tx_ref"}, status=404)

        # Now verify the payment status with Chapa
        chapa_response = verify_payment(tx_ref)
        print(f"Chapa verify response: {chapa_response}")

        status_chapa = chapa_response.get("data", {}).get("status")
        if status_chapa == "success":
            payment.status = "Completed"
            payment.save()
            print("Payment marked as Completed")

            # Send confirmation email (ensure Celery is running)
            # try:
            #     send_email_task.delay(payment.booking.user.email)
            # except Exception as e:
            #     print(f"Email sending error: {e}")

            return Response({"message": "Payment successful"}, status=200)
        else:
            payment.status = "Failed"
            payment.save()
            print("Payment marked as Failed")
            return Response({"message": "Payment failed"}, status=400)