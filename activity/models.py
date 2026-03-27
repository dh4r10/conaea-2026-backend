from django.db import models


class ActivityType(models.Model):
    name = models.CharField(max_length=20)
    logo = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'activity_types'


class Day(models.Model):
    date = models.DateTimeField()
    title = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'days'


class Speaker(models.Model):
    name = models.CharField(max_length=50)
    title = models.CharField(max_length=10)
    bio = models.TextField(null=True, blank=True)
    photo = models.FileField(upload_to='speakers/')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} {self.name}"

    class Meta:
        db_table = 'speakers'


class Activity(models.Model):
    activity_type = models.ForeignKey(
        ActivityType,
        on_delete=models.PROTECT,
        db_column='activity_type_id'
    )
    day = models.ForeignKey(
        Day,
        on_delete=models.PROTECT,
        db_column='day_id'
    )
    speaker = models.ForeignKey(
        Speaker,
        on_delete=models.PROTECT,
        db_column='speaker_id',
    )
    name = models.CharField(max_length=50)
    order = models.IntegerField()
    start_date = models.DateTimeField()
    duration = models.IntegerField()
    location = models.CharField(max_length=50)
    capacity = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        db_table = 'activities'
        ordering = ['order']