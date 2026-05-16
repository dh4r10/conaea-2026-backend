from django.urls import path, include
from rest_framework import routers
from .views import (
    AvailableSlotsSSEView,
    IndividualCupsSSEView,
    PreSaleViewSet,
    QuotaTypeViewSet,
    AvailableSlotViewSet,
    RegistrationViewSet,
    TransactionViewSet,
    RefundViewSet,
    DynamicCodeViewSet,
    IndividualCupViewSet,
    VerifyCodeView,
    InscriptionView,
    AvailableSlotsRealTimeView,
    ActivePhaseView,
    PhasesListView,
)

router = routers.DefaultRouter()

router.register('pre-sale', PreSaleViewSet, basename='pre_sale')
router.register('quota-type', QuotaTypeViewSet, basename='quota_type')
router.register('available-slot', AvailableSlotViewSet, basename='available_slot')
router.register('registration', RegistrationViewSet, basename='registration')
router.register('transaction', TransactionViewSet, basename='transaction')
router.register('refund', RefundViewSet, basename='refund')
router.register('dynamic-code', DynamicCodeViewSet, basename='dynamic_code')
router.register('individual-cup', IndividualCupViewSet, basename='individual_cup')

urlpatterns = [
    path('register/', include(router.urls)),
    path('register/verify-code/', VerifyCodeView.as_view(), name='verify_code'),
    path('register/inscription/', InscriptionView.as_view(), name='inscription'),
    path('available-slots/', AvailableSlotsRealTimeView.as_view(), name='available-slots'),
    path('available-slots/sse/', AvailableSlotsSSEView.as_view(), name='available-slots-sse'),
    path('individual-cups/sse/', IndividualCupsSSEView.as_view(), name='individual-cups-sse'),
    path('register/active-phase/', ActivePhaseView.as_view(), name='active-phase'),
    path('register/phases/', PhasesListView.as_view(), name='phases-list'),
]