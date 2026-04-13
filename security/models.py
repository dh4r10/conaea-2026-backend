from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class PersonalData(models.Model):
    dni = models.CharField(max_length=8, unique=True)
    first_name = models.CharField(max_length=50)
    paternal_surname = models.CharField(max_length=50)
    maternal_surname = models.CharField(max_length=50)
    phone = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.dni} - {self.first_name} {self.paternal_surname} {self.maternal_surname}"
    
    class Meta:
        db_table = 'personal_data'


class User(AbstractUser):
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    personal_data_id = models.OneToOneField('PersonalData', on_delete=models.CASCADE, db_column='personal_data_id')

    first_name = None
    last_name = None


class Validation(models.Model):
    MODEL_CHOICES = [
        ('enrollment', 'Enrollment'),
        ('transaction', 'Transaction'),
        ('registration', 'Registration'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column='user_id'
    )
    model = models.CharField(max_length=20, choices=MODEL_CHOICES)
    register_id = models.IntegerField()
    validated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.model} - {self.register_id} - {self.validated}"

    class Meta:
        db_table = 'validations'
        unique_together = ('model', 'register_id')  # un registro solo se valida una vez


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Enviado'),
        ('failed', 'Fallido'),
        ('pending', 'Pendiente'),
    ]

    TYPE_CHOICES = [
        ('inscription', 'Confirmación de inscripción'),
        ('payment', 'Confirmación de pago'),
        ('validation', 'Validación de participante'),
        ('reminder', 'Recordatorio'),
        ('custom', 'Personalizado'),
    ]

    participant = models.ForeignKey(
        'participant.Participant',
        on_delete=models.PROTECT,
        db_column='participant_id',
    )
    subject = models.CharField(max_length=200)
    email_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email_type} → {self.participant} ({self.status})"

    class Meta:
        db_table = 'email_logs'
        ordering = ['-created_at']