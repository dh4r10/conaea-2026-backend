import io
import string
import random
from PIL import Image
from django.db import models
from register.models import Registration, QuotaType
from django.core.files.base import ContentFile

def generate_partner_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits = ''.join(random.choices(string.digits, k=3))
    return letters + digits

def photograph_upload_path(instance, filename):
    return f'participants/{instance.identity_document}.webp'

class SpecialCondition(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'special_conditions'


class Participant(models.Model):
    registration = models.ForeignKey(
        Registration, 
        on_delete=models.CASCADE,
        db_column='registration_id',
    )
    photograph = models.ImageField(upload_to=photograph_upload_path)
    first_name = models.CharField(max_length=50)
    paternal_surname = models.CharField(max_length=50)
    maternal_surname = models.CharField(max_length=50)
    birthday = models.DateField()
    identity_document = models.CharField(max_length=10)
    document_type = models.CharField(max_length=20)
    cellphone = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)
    cod_country = models.IntegerField()
    cod_university = models.CharField(max_length=5)
    university_type = models.CharField(max_length=15)
    academic_cycle = models.CharField(max_length=4)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.identity_document} - {self.first_name} {self.paternal_surname}"
    
    def save(self, *args, **kwargs):
        if self.pk:
            old = Participant.objects.filter(pk=self.pk).first()
            if old and old.photograph == self.photograph:
                return super().save(*args, **kwargs)

        if self.photograph and hasattr(self.photograph, 'file'):
            img = Image.open(self.photograph)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=85)
            buffer.seek(0)
            self.photograph.save(
                f'{self.identity_document}.webp',
                ContentFile(buffer.read()),
                save=False
            )

        super().save(*args, **kwargs)

    class Meta:
        db_table = 'participants'
        ordering = ['-id']


class ParticipantSpecialCondition(models.Model):
    participant = models.ForeignKey(
        Participant, 
        on_delete=models.CASCADE,
        db_column='participant_id'
    )
    special_condition = models.ForeignKey(
        SpecialCondition, 
        on_delete=models.PROTECT,
        db_column='special_condition_id'
    )
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.participant} - {self.special_condition}"

    class Meta:
        db_table = 'participants_special_conditions'


class Enrollment(models.Model):
    participant = models.ForeignKey(
        Participant, 
        on_delete=models.CASCADE,
        db_column='participant_id'
    )
    type = models.CharField(max_length=10)
    archive = models.FileField(upload_to='enrollments/')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.participant} - {self.type}"

    class Meta:
        db_table = 'enrollments'


class PartnerUniversity(models.Model):
    id = models.BigAutoField(primary_key=True)

    code = models.CharField(
        max_length=5,
        unique=True,
        editable=False,
        null=True,
        blank=True
    )

    quota_type = models.ForeignKey(
        QuotaType,
        on_delete=models.CASCADE,
        db_column='quota_type_id',
    )
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10)
    place = models.CharField(max_length=20)
    country = models.CharField(max_length=30)
    region = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                new_code = generate_partner_code()
                if not PartnerUniversity.objects.filter(code=new_code).exists():
                    self.code = new_code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        db_table = 'partner_universities'


class Delegate(models.Model):
    partner_university = models.ForeignKey(
        PartnerUniversity,
        on_delete=models.CASCADE,
        db_column='partner_university_id',
        related_name='delegates'
    )
    type_delegate = models.CharField(max_length=15)
    fullname = models.CharField(max_length=100)
    cellphone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.fullname} - {self.partner_university_id}"

    class Meta:
        db_table = 'delegates'