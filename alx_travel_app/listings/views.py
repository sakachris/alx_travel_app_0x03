# listings/views.py

import logging
import time
from django.conf import settings
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Property, Booking, Payment
from .serializers import InitiatePaymentSerializer, PropertySerializer, BookingSerializer
from .chapa import initiate_payment, verify_payment
from .tasks import send_payment_confirmation_email, send_booking_confirmation_email
from rest_framework import viewsets
from rest_framework import status
from django.core.mail import send_mail


logger = logging.getLogger(__name__)

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

    # def perform_create(self, serializer):
    #     booking = serializer.save()
    #     send_email_task.delay(booking.user.email)
    
    def perform_create(self, serializer):
        booking = serializer.save()
        send_booking_confirmation_email.delay(
            to_email=booking.user.email,
            property_name=booking.property.name,
            start_date=str(booking.start_date),
            end_date=str(booking.end_date),
            total_price=str(booking.total_price)
        )


# class InitiatePaymentView(APIView):
#     """
#     Initiates a payment request to Chapa for a given booking.
#     """

#     def post(self, request):
#         serializer = InitiatePaymentSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=400)

#         booking_id = serializer.validated_data["booking_id"]
#         logger.info(f"Initiating payment for booking_id: {booking_id}")

#         try:
#             booking = Booking.objects.get(booking_id=booking_id)
#         except Booking.DoesNotExist:
#             return Response({"error": "Booking not found"}, status=404)

#         amount = str(booking.total_price)
#         tx_ref = f"chapa-{booking.booking_id}"
#         email = booking.user.email
#         first_name = booking.user.first_name
#         last_name = booking.user.last_name

#         chapa_data = {
#             "amount": amount,
#             "currency": settings.DEFAULT_CURRENCY,
#             "email": email,
#             "first_name": first_name,
#             "last_name": last_name,
#             "tx_ref": tx_ref,
#             "callback_url": settings.CHAPA_CALLBACK_URL,
#             "return_url": settings.CHAPA_RETURN_URL,
#             "customization[title]": "Property Booking",
#         }

#         logger.info(f"Sending payment data to Chapa: {chapa_data}")
#         chapa_response = initiate_payment(chapa_data)
#         logger.info(f"Chapa Response: {chapa_response}")

#         if chapa_response.get("status") == "success":
#             with transaction.atomic():
#                 Payment.objects.get_or_create(
#                     booking=booking,
#                     transaction_id=tx_ref,
#                     defaults={
#                         "amount": amount,
#                         "status": "Pending",
#                     }
#                 )
#             return Response({
#                 "checkout_url": chapa_response["data"]["checkout_url"],
#                 "transaction_id": tx_ref
#             }, status=200)
#         else:
#             return Response({
#                 "error": "Payment initiation failed",
#                 "details": chapa_response
#             }, status=400)


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

# class VerifyPaymentView(APIView):
#     """
#     Verifies the payment after Chapa redirects back.
#     """

#     def get(self, request):
#         query = request.query_params
#         logger.info(f"Chapa returned to verify URL with: {dict(query)}")

#         tx_ref = query.get("tx_ref") or query.get("trx_ref") or query.get("transaction_id")
#         if not tx_ref:
#             return Response({"error": "Missing transaction_id or tx_ref"}, status=400)

#         time.sleep(2)  # Optional: wait for Chapa to finalize

#         try:
#             payment = Payment.objects.get(transaction_id=tx_ref)
#             logger.info(f"Found existing payment: {payment}")
#         except Payment.DoesNotExist:
#             logger.warning(f"Payment with tx_ref {tx_ref} not found. Attempting fallback creation.")
#             try:
#                 booking_id = tx_ref.replace("chapa-", "")
#                 booking = Booking.objects.get(booking_id=booking_id)
#                 payment = Payment.objects.create(
#                     booking=booking,
#                     amount=booking.total_price,
#                     transaction_id=tx_ref,
#                     status="Pending"
#                 )
#                 logger.info(f"Created fallback payment record for booking {booking_id}")
#             except Booking.DoesNotExist:
#                 return Response({"error": f"No booking found for tx_ref {tx_ref}"}, status=404)

#         chapa_response = verify_payment(tx_ref)
#         logger.info(f"Chapa verify response: {chapa_response}")

#         status_chapa = chapa_response.get("data", {}).get("status")

#         with transaction.atomic():
#             if status_chapa == "success":
#                 payment.status = "Completed"
#                 payment.save()
#                 logger.info("Payment marked as Completed")

#                 try:
#                     # send_email_task.delay(payment.booking.user.email)
#                     send_payment_confirmation_email.delay(
#                         to_email=payment.booking.user.email,
#                         property_name=payment.booking.property.title,
#                         start_date=str(payment.booking.start_date),
#                         end_date=str(payment.booking.end_date),
#                         amount=payment.amount
#                     )
#                 except Exception as e:
#                     logger.error(f"Error sending email: {e}")

#                 # return Response({"message": "Payment successful"}, status=200)
#                 return Response({
#                     "message": "✅ Payment verified and booking confirmed.",
#                     "booking": {
#                         "property": payment.booking.property.title,
#                         "start_date": str(payment.booking.start_date),
#                         "end_date": str(payment.booking.end_date),
#                         "amount": str(payment.amount)
#                     },
#                     "email_sent": True
#                 }, status=status.HTTP_200_OK)

#             else:
#                 payment.status = "Failed"
#                 payment.save()
#                 logger.warning("Payment marked as Failed")
#                 return Response({"message": "Payment failed"}, status=400)
            

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

# class SuccessPaymentView(APIView):
#     """
#     This view is used as the return_url after a successful payment.
#     Chapa redirects the user here after completing payment.
#     """

#     def get(self, request):
#         tx_ref = request.query_params.get("tx_ref")

#         if not tx_ref:
#             return Response({"error": "Missing transaction reference (tx_ref)."}, status=400)

#         try:
#             payment = Payment.objects.select_related("booking__property", "booking__user").get(transaction_id=tx_ref)
#         except Payment.DoesNotExist:
#             return Response({"error": f"No payment found with transaction ID: {tx_ref}"}, status=404)

#         if payment.status != "Completed":
#             return Response({
#                 "message": "Payment received but not yet verified. Please check again later.",
#                 "status": payment.status
#             }, status=202)

#         booking = payment.booking
#         return Response({
#             "message": "🎉 Payment Successful and Booking Confirmed!",
#             "payment": {
#                 "transaction_id": tx_ref,
#                 "amount": str(payment.amount),
#                 "status": payment.status
#             },
#             "booking": {
#                 "property": booking.property.title,
#                 "start_date": str(booking.start_date),
#                 "end_date": str(booking.end_date),
#                 "user": booking.user.email
#             }
#         }, status=status.HTTP_200_OK)

# from rest_framework import viewsets
# from .models import Property, Booking, Payment
# from .serializers import PropertySerializer, BookingSerializer, PaymentSerializer
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from .chapa import initiate_payment, verify_payment
# from django.conf import settings
# from django.core.mail import send_mail
# from .tasks import send_email_task, send_booking_confirmation_email 
# import time


# class PropertyViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for managing Property instances.

#     Provides standard CRUD actions (list, retrieve, create, update, delete)
#     for the Property model.
#     """

#     queryset = Property.objects.all()
#     serializer_class = PropertySerializer


# class BookingViewSet(viewsets.ModelViewSet):
#     queryset = Booking.objects.all()
#     serializer_class = BookingSerializer

#     # def perform_create(self, serializer):
#     #     booking = serializer.save()
#     #     send_email_task.delay(booking.user.email)
    
#     def perform_create(self, serializer):
#         booking = serializer.save()
#         send_booking_confirmation_email.delay(
#             to_email=booking.user.email,
#             property_name=booking.property.name,
#             start_date=str(booking.start_date),
#             end_date=str(booking.end_date),
#             total_price=str(booking.total_price)
#         )


# class InitiatePaymentView(APIView):
#     """
#     Initiates a payment request to Chapa for a given booking.
#     """
#     def post(self, request):
#         booking_id = request.data.get("booking_id")
#         print(f"Initiating payment for booking_id: {booking_id}")

#         try:
#             booking = Booking.objects.get(booking_id=booking_id)
#         except Booking.DoesNotExist:
#             return Response({"error": "Booking not found"}, status=404)

#         amount = str(booking.total_price)
#         tx_ref = f"chapa-{booking.booking_id}"
#         email = booking.user.email
#         first_name = booking.user.first_name
#         last_name = booking.user.last_name

#         # Return and callback URLs can be the same
#         callback_url = "http://127.0.0.1:8000/api/payment/verify/"
#         return_url = "http://127.0.0.1:8000/api/"

#         chapa_data = {
#             "amount": amount,
#             "currency": "ETB",
#             "email": email,
#             "first_name": first_name,
#             "last_name": last_name,
#             "tx_ref": tx_ref,
#             "callback_url": callback_url,
#             "return_url": callback_url,
#             "customization[title]": "Property Booking",
#         }

#         print(f"Sending payment data to Chapa: {chapa_data}")
#         chapa_response = initiate_payment(chapa_data)
#         print(f"Chapa Response: {chapa_response}")

#         if chapa_response.get("status") == "success":
#             Payment.objects.create(
#                 booking=booking,
#                 amount=amount,
#                 transaction_id=tx_ref,
#                 status="Pending",
#             )
#             return Response({
#                 "checkout_url": chapa_response["data"]["checkout_url"],
#                 "transaction_id": tx_ref
#             }, status=200)
#         else:
#             return Response({"error": "Payment initiation failed", "details": chapa_response}, status=400)


# class VerifyPaymentView(APIView):
#     def get(self, request):
#         query = request.query_params
#         print("✅ Chapa returned to verify URL with:", dict(query))

#         tx_ref = query.get("tx_ref") or query.get("trx_ref") or query.get("transaction_id")
#         if not tx_ref:
#             return Response({"error": "Missing transaction_id or tx_ref"}, status=400)

#         time.sleep(2)  # Give Chapa time to finalize

#         try:
#             payment = Payment.objects.get(transaction_id=tx_ref)
#             print(f"✅ Found existing payment: {payment}")
#         except Payment.DoesNotExist:
#             print(f"⚠️ Payment with tx_ref {tx_ref} not found. Attempting to create from booking...")
#             try:
#                 booking_id = tx_ref.replace("chapa-", "")
#                 booking = Booking.objects.get(booking_id=booking_id)
#                 payment = Payment.objects.create(
#                     booking=booking,
#                     amount=booking.total_price,
#                     transaction_id=tx_ref,
#                     status="Pending"
#                 )
#                 print(f"✅ Created fallback payment record for booking {booking_id}")
#             except Booking.DoesNotExist:
#                 return Response({"error": f"No booking found for tx_ref {tx_ref}"}, status=404)

#         chapa_response = verify_payment(tx_ref)
#         print(f"🔁 Chapa verify response: {chapa_response}")

#         status_chapa = chapa_response.get("data", {}).get("status")
#         if status_chapa == "success":
#             payment.status = "Completed"
#             payment.save()
#             print("✅ Payment marked as Completed")

#             try:
#                 send_email_task.delay(payment.booking.user.email)
#             except Exception as e:
#                 print(f"⚠️ Email sending error: {e}")

#             return Response({"message": "Payment successful"}, status=200)
#         else:
#             payment.status = "Failed"
#             payment.save()
#             print("❌ Payment marked as Failed")
#             return Response({"message": "Payment failed"}, status=400)
        

# class VerifyPaymentView(APIView):
#     """
#     Verifies the payment status with Chapa and updates the Payment model.
#     """
#     def get(self, request):
#         query = request.query_params
#         print("Received Chapa verify callback with query params:", dict(query))

#         tx_ref = query.get("trx_ref") or query.get("transaction_id")
#         if not tx_ref:
#             return Response({"error": "Missing transaction_id or trx_ref"}, status=400)

#         # Sleep to avoid race condition (payment not saved yet)
#         time.sleep(2)

#         # Try to fetch existing payment
#         try:
#             payment = Payment.objects.get(transaction_id=tx_ref)
#             print(f"Found payment: {payment}")
#         except Payment.DoesNotExist:
#             print(f"Payment with tx_ref {tx_ref} not found. Attempting to recover from booking...")
#             try:
#                 booking_id = tx_ref.replace("chapa-", "")
#                 booking = Booking.objects.get(booking_id=booking_id)
#                 payment = Payment.objects.create(
#                     booking=booking,
#                     amount=booking.total_price,
#                     transaction_id=tx_ref,
#                     status="Pending"
#                 )
#                 print(f"Created fallback payment record for booking: {booking_id}")
#             except Booking.DoesNotExist:
#                 return Response({"error": "No booking found for tx_ref"}, status=404)

#         # Now verify the payment status with Chapa
#         chapa_response = verify_payment(tx_ref)
#         print(f"Chapa verify response: {chapa_response}")

#         status_chapa = chapa_response.get("data", {}).get("status")
#         if status_chapa == "success":
#             payment.status = "Completed"
#             payment.save()
#             print("Payment marked as Completed")

#             # Send confirmation email (ensure Celery is running)
#             try:
#                 send_email_task.delay(payment.booking.user.email)
#             except Exception as e:
#                 print(f"Email sending error: {e}")

#             return Response({"message": "Payment successful"}, status=200)
#         else:
#             payment.status = "Failed"
#             payment.save()
#             print("Payment marked as Failed")
#             return Response({"message": "Payment failed"}, status=400)