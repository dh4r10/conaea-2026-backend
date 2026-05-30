from django.urls import path, include
from rest_framework import routers
from .views import (
    ActivityTypeViewSet,
    DayViewSet,
    SpeakerViewSet,
    ActivityViewSet,
    ScheduleView,
)

router = routers.DefaultRouter()

router.register('activity-type', ActivityTypeViewSet, basename='activity_type')
router.register('day', DayViewSet, basename='day')
router.register('speaker', SpeakerViewSet, basename='speaker')
router.register('activity', ActivityViewSet, basename='activity')

urlpatterns = [
    path('activities/', include(router.urls)),
    path('schedule/', ScheduleView.as_view(), name='schedule'),
]