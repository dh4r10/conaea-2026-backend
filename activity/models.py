import os
import io
from django.db import models
from django.core.files.base import ContentFile
from PIL import Image
import unicodedata

def speaker_upload_path(instance, filename):
    # Genera el nombre: speakers/juan_perez.webp
    clean_name = instance.name.lower().strip().replace(' ', '_')
    return f'speakers/{clean_name}.webp'

def clean_filename(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name)
    ascii_name = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_name.lower().strip().replace(' ', '_')

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
    photo = models.ImageField(upload_to=speaker_upload_path)  # 👈 ImageField + función
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} {self.name}"

    def save(self, *args, **kwargs):
    # Detectar si es update
        if self.pk:
            old = Speaker.objects.filter(pk=self.pk).first()

            # Si la imagen NO cambió → no hacer nada
            if old and old.photo == self.photo:
                return super().save(*args, **kwargs)

        # Solo si hay nueva imagen
        if self.photo and hasattr(self.photo, 'file'):
            img = Image.open(self.photo)

            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')

            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=85)
            buffer.seek(0)

            clean_name = clean_filename(self.name)

            self.photo.save(
                f'{clean_name}.webp',
                ContentFile(buffer.read()),
                save=False
            )

        super().save(*args, **kwargs)
        
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