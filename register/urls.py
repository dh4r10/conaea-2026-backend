from django.urls import path, include
from rest_framework import routers
from .views import (
    PreSaleViewSet,
    QuotaTypeViewSet,
    AvailableSlotViewSet,
    RegistrationViewSet,
    TransactionViewSet,
    RefundViewSet,
)

router = routers.DefaultRouter()

router.register('pre-sale', PreSaleViewSet, basename='pre_sale')
router.register('quota-type', QuotaTypeViewSet, basename='quota_type')
router.register('available-slot', AvailableSlotViewSet, basename='available_slot')
router.register('registration', RegistrationViewSet, basename='registration')
router.register('transaction', TransactionViewSet, basename='transaction')
router.register('refund', RefundViewSet, basename='refund')

urlpatterns = [
    path('register/', include(router.urls)),
]