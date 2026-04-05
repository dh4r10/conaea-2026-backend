from django.urls import path, include
from rest_framework import routers
from .views import (
    SpecialConditionViewSet,
    ParticipantViewSet,
    ParticipantSpecialConditionViewSet,
    EnrollmentViewSet,
    ParticipantValidationView,
    PartnerUniversityViewSet,
    DelegateViewSet,
    ParticipantByDNIView
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
    path('participants/by-dni/', ParticipantByDNIView.as_view(), name='participant_by_dni'),
]