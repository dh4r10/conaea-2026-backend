from django.urls import path, include
from rest_framework import routers
from .views import (
    ParticipantStatsView,
    ParticipantTableView,
    ParticipantUpdateView,
    ParticipantProfileView,
    SpecialConditionViewSet,
    ParticipantViewSet,
    ParticipantSpecialConditionViewSet,
    EnrollmentViewSet,
    ParticipantValidationView,
    PartnerUniversityViewSet,
    DelegateViewSet,
    ParticipantByIdentityView,
    RequestOTPView,
    VerifyOTPView,
)

router = routers.DefaultRouter()

router.register('special-condition', SpecialConditionViewSet, basename='special_condition')
router.register('participant', ParticipantViewSet, basename='participant')
router.register('participant-special-condition', ParticipantSpecialConditionViewSet, basename='participant_special_condition')
router.register('enrollment', EnrollmentViewSet, basename='enrollment')
router.register('partner-universities', PartnerUniversityViewSet, basename='partner_university')
router.register('delegates', DelegateViewSet, basename='delegate')

urlpatterns = [
    path('participants/', include(router.urls)),
    path('participants/validate/', ParticipantValidationView.as_view(), name='participant_validate'),
    path('participants/by-identity/request-otp/', RequestOTPView.as_view(), name='participant_request_otp'),
    path('participants/by-identity/verify-otp/', VerifyOTPView.as_view(), name='participant_verify_otp'),
    path('participants/by-identity/', ParticipantByIdentityView.as_view(), name='participant_by_identity'),
    path('participants/table/', ParticipantTableView.as_view(), name='participant-table'),
    path('participants/stats/', ParticipantStatsView.as_view(), name='participant_stats'),
    path('participants/participant/<int:pk>/update/', ParticipantUpdateView.as_view(), name='participant_update'),
    path('participants/<int:participant_id>/profile/', ParticipantProfileView.as_view(), name='participant_profile'),
]