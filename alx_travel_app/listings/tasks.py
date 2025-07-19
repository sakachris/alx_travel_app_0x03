# listings/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_email_task(recipient):
    send_mail(
        subject="Booking Confirmed!",
        message="Your payment was successful and your booking is confirmed.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )


@shared_task
def send_booking_confirmation_email(to_email, property_name, start_date, end_date, total_price):
    subject = 'Booking Confirmation'
    message = (
        f"Your booking for {property_name} from {start_date} to {end_date} "
        f"has been submitted. Total Price: KES {total_price}."
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )


@shared_task
def send_payment_confirmation_email(to_email, property_name, start_date, end_date, amount):
    subject = 'Payment Confirmation Successful'
    message = (
        f"Dear Customer,\n\n"
        f"Your booking for '{property_name}' from {start_date} to {end_date} "
        f"has been confirmed.\n\n"
        f"Total amount paid: KES {amount}.\n\n"
        f"Thank you for booking with us!\n"
        f"— ALX Travel App Team"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False
    )