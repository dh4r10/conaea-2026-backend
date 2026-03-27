from django.urls import path, include
from rest_framework import routers
from .views import (
    SpecialConditionViewSet,
    ParticipantViewSet,
    ParticipantSpecialConditionViewSet,
    EnrollmentViewSet,
    ParticipantValidationView
)

router = routers.DefaultRouter()

router.register('special-condition', SpecialConditionViewSet, basename='special_condition')
router.register('participant', ParticipantViewSet, basename='participant')
router.register('participant-special-condition', ParticipantSpecialConditionViewSet, basename='participant_special_condition')
router.register('enrollment', EnrollmentViewSet, basename='enrollment')

urlpatterns = [
    path('participants/', include(router.urls)),
    path('participants/validate/', ParticipantValidationView.as_view(), name='participant_validate'),
]