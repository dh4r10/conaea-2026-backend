import re

from rest_framework import serializers
from .models import SpecialCondition, Participant, ParticipantSpecialCondition, Enrollment, PartnerUniversity, Delegate
from register.serializers import QuotaTypeSerializer


class SpecialConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialCondition
        fields = '__all__'


class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = '__all__'


class ParticipantSpecialConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipantSpecialCondition
        fields = '__all__'


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = '__all__'


class ParticipantDetailSerializer(serializers.ModelSerializer):
    """Serializer con datos anidados para lectura"""
    special_conditions = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = '__all__'

    def get_special_conditions(self, obj):
        conditions = ParticipantSpecialCondition.objects.filter(
            participant=obj, 
            is_active=True
        )
        return ParticipantSpecialConditionSerializer(conditions, many=True).data

    def get_enrollments(self, obj):
        enrollments = Enrollment.objects.filter(
            participant=obj,
            is_active=True
        )
        return EnrollmentSerializer(enrollments, many=True).data
    
class PartnerUniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerUniversity
        fields = '__all__'
        read_only_fields = ['id', 'code']  # se genera automáticamente

class DelegateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Delegate
        fields = '__all__'

class PartnerUniversityDetailSerializer(serializers.ModelSerializer):
    delegates = serializers.SerializerMethodField()
    quota_type = QuotaTypeSerializer(read_only=True)  # 👈 muestra nombre en vez de ID

    class Meta:
        model = PartnerUniversity
        fields = '__all__'

    def get_delegates(self, obj):
        delegates = obj.delegates.filter(is_active=True)
        return DelegateSerializer(delegates, many=True).data

class ParticipantValidationSerializer(serializers.Serializer):
    first_name = serializers.CharField(
        max_length=50,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
            'max_length': 'Máximo 50 caracteres'
        }
    )
    paternal_surname = serializers.CharField(
        max_length=50,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
            'max_length': 'Máximo 50 caracteres'
        }
    )
    maternal_surname = serializers.CharField(
        max_length=50,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
            'max_length': 'Máximo 50 caracteres'
        }
    )
    identity_document = serializers.CharField(
        max_length=10,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
        }
    )
    document_type = serializers.ChoiceField(
        choices=['DNI', 'PASAPORTE'],
        error_messages={
            'invalid_choice': 'Solo se permite DNI o PASAPORTE',
            'required': 'Este campo es requerido',
        }
    )
    email = serializers.EmailField(
        max_length=255,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
            'invalid': 'Ingrese un email válido',
            'max_length': 'Máximo 255 caracteres'
        }
    )
    cod_country = serializers.IntegerField(
        error_messages={
            'required': 'Este campo es requerido',
            'invalid': 'Debe ser un número entero'
        }
    )
    cod_university = serializers.IntegerField(
        error_messages={
            'required': 'Este campo es requerido',
            'invalid': 'Debe ser un número entero'
        }
    )
    academic_cycle = serializers.CharField(
        max_length=4,
        error_messages={
            'required': 'Este campo es requerido',
        }
    )
    birthdate = serializers.DateField(
        error_messages={
            'required': 'Este campo es requerido',
        }
    )
    archive = serializers.FileField(
        error_messages={
            'required': 'La ficha de matrícula es requerida',
            'invalid': 'Archivo inválido'
        }
    )
    allergy = serializers.CharField(
        error_messages={
            'required': 'Este campo es requerido',
            'invalid': 'Este campo es requerido',
            'blank': 'La alergía es requerida'
        }
    )
    disability = serializers.CharField(
        error_messages={
            'required': 'Este campo es requerido',
            'invalid': 'Este campo es requerido',
            'blank': 'La discapacidad es requerida'
        }
    )

    def validate_first_name(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value

    def validate_paternal_surname(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value

    def validate_maternal_surname(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value

    def validate_identity_document(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Solo se permiten números')
        return value

    def validate_archive(self, value):
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError('Solo se permiten archivos PDF')
        return value

    def validate(self, data):
        document_type = data.get('document_type')
        identity_document = data.get('identity_document')

        if document_type == 'DNI' and len(identity_document) != 8:
            raise serializers.ValidationError({
                'identity_document': 'El DNI debe tener exactamente 8 dígitos'
            })
        if document_type == 'PASAPORTE' and len(identity_document) > 10:
            raise serializers.ValidationError({
                'identity_document': 'El pasaporte debe tener máximo 10 dígitos'
            })
        return data