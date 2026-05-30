from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ActivityType, Day, Speaker, Activity
from .serializers import (
    ActivityTypeSerializer,
    DaySerializer,
    DayDetailSerializer,
    SpeakerSerializer,
    ActivitySerializer,
    ActivityDetailSerializer,
    ScheduleSerializer,
)


class ActivityTypeViewSet(viewsets.ModelViewSet):
    queryset = ActivityType.objects.filter(is_active=True)
    serializer_class = ActivityTypeSerializer
    permission_classes = [permissions.AllowAny]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            activity_count = Activity.objects.filter(activity_type=instance, is_active=True).count()
            if activity_count:
                return Response(
                    {'detail': f'No se puede desactivar el tipo de actividad porque tiene {activity_count} actividad{"es" if activity_count != 1 else ""} asociada{"s" if activity_count != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return super().update(request, *args, **kwargs)


class DayViewSet(viewsets.ModelViewSet):
    queryset = Day.objects.filter(is_active=True).order_by('date')
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            activity_count = Activity.objects.filter(day=instance, is_active=True).count()
            if activity_count:
                return Response(
                    {'detail': f'No se puede desactivar el día porque tiene {activity_count} actividad{"es" if activity_count != 1 else ""} asociada{"s" if activity_count != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return super().update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DayDetailSerializer
        return DaySerializer

    @action(detail=True, methods=['get'], url_path='activities')
    def activities(self, request, pk=None):
        """
        Obtener actividades de un día
        GET /api/activities/day/{id}/activities/
        """
        day = self.get_object()
        activities = Activity.objects.filter(
            day=day,
            is_active=True
        ).order_by('order')
        serializer = ActivityDetailSerializer(activities, many=True)
        return Response(serializer.data)


class SpeakerViewSet(viewsets.ModelViewSet):
    queryset = Speaker.objects.filter(is_active=True)
    serializer_class = SpeakerSerializer
    permission_classes = [permissions.AllowAny]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            activity_count = Activity.objects.filter(speaker=instance, is_active=True).count()
            if activity_count:
                return Response(
                    {'detail': f'No se puede desactivar el ponente porque tiene {activity_count} actividad{"es" if activity_count != 1 else ""} asociada{"s" if activity_count != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return super().update(request, *args, **kwargs)


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.filter(is_active=True).order_by('order')
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        # 👈 list y retrieve usan el serializer de detalle
        if self.action in ('list', 'retrieve'):
            return ActivityDetailSerializer
        return ActivitySerializer

    def get_queryset(self):
        queryset = Activity.objects.filter(is_active=True).order_by('order')
        day_id = self.request.query_params.get('day_id')
        activity_type_id = self.request.query_params.get('activity_type_id')
        speaker_id = self.request.query_params.get('speaker_id')
        if day_id:
            queryset = queryset.filter(day_id=day_id)
        if activity_type_id:
            queryset = queryset.filter(activity_type_id=activity_type_id)
        if speaker_id:
            queryset = queryset.filter(speaker_id=speaker_id)
        return queryset


class ScheduleView(generics.ListAPIView):
    queryset = Day.objects.filter(is_active=True).order_by('date')
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.AllowAny]