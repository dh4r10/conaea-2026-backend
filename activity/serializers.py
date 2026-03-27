from rest_framework import serializers
from .models import ActivityType, Day, Speaker, Activity


class ActivityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityType
        fields = '__all__'


class DaySerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(
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