# listings/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PropertyViewSet, BookingViewSet, CustomTokenObtainPairView, InitiatePaymentView, VerifyPaymentView, SuccessPaymentView, RegisterView, PropertyReviewListView, ReviewCreateView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)

# Create a router and register viewsets
router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"bookings", BookingViewSet, basename="booking")

urlpatterns = [
    path("", include(router.urls)),
    path('signup/', RegisterView.as_view(), name='signup'),
    # path('signin/', TokenObtainPairView.as_view(), name='signin'),
    path('signin/', CustomTokenObtainPairView.as_view(), name='signin'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('payment/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('payment/verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('payment/success/', SuccessPaymentView.as_view(), name='success-payment'),
    path("properties/<uuid:property_id>/reviews/", PropertyReviewListView.as_view()),
    path("reviews/add/", ReviewCreateView.as_view()),
]