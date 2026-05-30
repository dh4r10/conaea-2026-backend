from rest_framework import serializers
from .models import ActivityType, Day, Speaker, Activity

_DAYS_ES = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
_MONTHS_ES = {1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'}


def _format_duration(minutes):
    if minutes < 60:
        return f"{minutes}min"
    hours, remaining = divmod(minutes, 60)
    return f"{hours}h" if remaining == 0 else f"{hours}h {remaining}min"


class ActivityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityType
        fields = '__all__'


class DaySerializer(serializers.ModelSerializer):
    date = serializers.DateField(
        required=False,
        allow_null=True,
        default=None
    )

    class Meta:
        model = Day
        fields = '__all__'


class SpeakerSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = Speaker
        fields = '__all__'


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = '__all__'


class ActivityDetailSerializer(serializers.ModelSerializer):
    activity_type = ActivityTypeSerializer(read_only=True)
    day = DaySerializer(read_only=True)
    speaker = SpeakerSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = '__all__'


class DayDetailSerializer(serializers.ModelSerializer):
    activities = serializers.SerializerMethodField()

    class Meta:
        model = Day
        fields = '__all__'

    def get_activities(self, obj):
        activities = Activity.objects.filter(
            day=obj,
            is_active=True
        ).order_by('order')
        return ActivityDetailSerializer(activities, many=True).data


class ScheduleActivitySerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    title = serializers.CharField(source='name')
    type = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = ['time', 'duration', 'title', 'location', 'type', 'description']

    def get_time(self, obj):
        return obj.start_date.strftime('%H:%M')

    def get_duration(self, obj):
        return _format_duration(obj.duration)

    def get_type(self, obj):
        return obj.activity_type.name.lower()

    def get_description(self, obj):
        return None


class ScheduleSerializer(serializers.ModelSerializer):
    day_name = serializers.SerializerMethodField()
    day_num = serializers.SerializerMethodField()
    month = serializers.SerializerMethodField()
    theme = serializers.CharField(source='title')
    activities = serializers.SerializerMethodField()

    class Meta:
        model = Day
        fields = ['date', 'day_name', 'day_num', 'month', 'theme', 'activities']

    def get_day_name(self, obj):
        return _DAYS_ES[obj.date.weekday()]

    def get_day_num(self, obj):
        return str(obj.date.day)

    def get_month(self, obj):
        return _MONTHS_ES[obj.date.month]

    def get_activities(self, obj):
        activities = (
            Activity.objects
            .filter(day=obj, is_active=True)
            .select_related('activity_type')
            .order_by('order')
        )
        return ScheduleActivitySerializer(activities, many=True).data