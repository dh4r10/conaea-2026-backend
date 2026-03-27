from django.db import models
from register.models import Registration

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
    first_name = models.CharField(max_length=50)
    paternal_surname = models.CharField(max_length=50)
    maternal_surname = models.CharField(max_length=50)
    birthday = models.DateField()
    identity_document = models.CharField(max_length=10, unique=True)
    document_type = models.CharField(max_length=20)
    email = models.EmailField(max_length=255, unique=True)
    cod_country = models.IntegerField()
    cod_university = models.IntegerField()
    academic_cycle = models.CharField(max_length=4)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.identity_document} - {self.first_name} {self.paternal_surname}"

    class Meta:
        db_table = 'participants'


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