import re
import phonenumbers
from phonenumbers import NumberParseException
from rest_framework import serializers
from .models import SpecialCondition, Participant, ParticipantSpecialCondition, Enrollment, PartnerUniversity, Delegate
from register.models import Transaction
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
    photograph = serializers.ImageField(
        error_messages={
            'required': 'La fotografía es requerida',
            'invalid': 'Archivo de imagen inválido'
        }
    )

    def validate_photograph(self, value):
        valid_extensions = ('.jpg', '.jpeg', '.png')
        if not value.name.lower().endswith(valid_extensions):
            raise serializers.ValidationError('Solo se permiten imágenes JPG o PNG')
        if value.size > 500 * 1024:
            raise serializers.ValidationError('La fotografía no debe superar los 500 KB')
        return value

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
            'max_length': 'Máximo 10 caracteres'
        }
    )
    document_type = serializers.ChoiceField(
        choices=['DNI', 'PASAPORTE'],
        error_messages={
            'invalid_choice': 'Solo se permite DNI o PASAPORTE',
            'required': 'Este campo es requerido',
        }
    )
    cellphone = serializers.CharField(
        max_length=20,
        error_messages={
            'blank': 'Este campo no puede estar vacío',
            'required': 'Este campo es requerido',
            'max_length': 'Máximo 20 caracteres'
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
    # Solo requerido en General, en Referido se omite o llega '---'
    cod_country = serializers.IntegerField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Debe ser un número entero'
        }
    )
    # CharField porque en Referido es el code (ej. 'AB123')
    # y en General es el código que envía el frontend
    cod_university = serializers.CharField(
        max_length=5,
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': 'Máximo 5 caracteres'
        }
    )
    academic_cycle = serializers.CharField(
        max_length=4,
        required=False,       # 👈
        allow_blank=True,
        default='0',
        error_messages={
            'max_length': 'Máximo 4 caracteres'
        }
    )
    birthdate = serializers.DateField(
        error_messages={
            'required': 'Este campo es requerido',
            'invalid': 'Ingrese una fecha válida (YYYY-MM-DD)'
        }
    )
    # Se valida manualmente en la view, pero se incluye aquí para validar formato PDF
    archive = serializers.FileField(
        required=False,       # 👈 la view ya lo valida condicionalmente
        error_messages={
            'invalid': 'Archivo inválido'
        }
    )
    # Opcionales — se omiten si vienen vacíos
    discapacidad = serializers.CharField(
        required=False,
        allow_blank=True,
        default=''
    )
    alergia = serializers.CharField(
        required=False,
        allow_blank=True,
        default=''
    )

    # ── Validaciones de campo ──────────────────────────────────────────

    def validate_first_name(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value.strip()

    def validate_paternal_surname(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value.strip()

    def validate_maternal_surname(self, value):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$', value):
            raise serializers.ValidationError('Solo se permiten letras')
        return value.strip()

    def validate_identity_document(self, value):
        document_type = self.initial_data.get('document_type', '')
        
        if document_type == 'DNI' and not value.isdigit():
            raise serializers.ValidationError('Solo se permiten números')
        
        return value

    def validate_archive(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError('Solo se permiten archivos PDF')
        if value.size > 300 * 1024:
            raise serializers.ValidationError('El archivo no debe superar los 300 KB')
        return value
    
    def validate_cellphone(self, value):
        """
        Valida el número telefónico y lo formatea como:
        (+CC) NNNNNNNNN
        Ejemplo: (+51) 987654321
        """
        if not value:
            raise serializers.ValidationError('Este campo es requerido')

        # Acepta formatos como +51-987654321 o +51987654321
        normalized = value.replace('-', '').replace(' ', '')

        try:
            parsed = phonenumbers.parse(normalized, None)
        except NumberParseException:
            raise serializers.ValidationError('Número de teléfono inválido')

        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError(
                'Número de teléfono inválido para el país indicado'
            )

        # Obtener código de país y número nacional
        country_code = parsed.country_code
        national_number = parsed.national_number

        # Formato personalizado con paréntesis
        formatted_number = f"(+{country_code}){national_number}"

        return formatted_number

    # ── Validaciones cruzadas ──────────────────────────────────────────

    def validate(self, data):
        document_type = data.get('document_type')
        identity_document = data.get('identity_document', '')

        if document_type == 'DNI' and len(identity_document) != 8:
            raise serializers.ValidationError({
                'identity_document': 'El DNI debe tener exactamente 8 dígitos'
            })
        if document_type == 'PASAPORTE' and len(identity_document) > 10:
            raise serializers.ValidationError({
                'identity_document': 'El pasaporte debe tener máximo 10 dígitos'
            })

        return data
    

class ParticipantTableSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    university_name = serializers.SerializerMethodField()
    quota_type = serializers.SerializerMethodField()
    pre_sale = serializers.SerializerMethodField()
    vouchers = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()
    is_validated = serializers.SerializerMethodField()

    class Meta:
        model = Participant
        fields = [
            'id',
            'document_type',
            'identity_document',
            'photograph',
            'full_name',
            'university_type',
            'university_name',
            'cellphone',
            'quota_type',
            'pre_sale',
            'vouchers',
            'enrollments',
            'is_validated', 
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.paternal_surname} {obj.maternal_surname}"

    def get_university_name(self, obj):
        if obj.university_type == 'Referido':
            university = self.context.get('universities', {}).get(obj.cod_university)
            return university.name if university else obj.cod_university
        return obj.cod_university

    def get_quota_type(self, obj):
        return obj.registration.quota_type.name

    def get_pre_sale(self, obj):
        return obj.registration.pre_sale.name

    def get_vouchers(self, obj):
        request = self.context.get('request')
        validations = self.context.get('validations', set())  # 👈
        transactions = Transaction.objects.filter(
            registration=obj.registration,
            is_active=True
        )
        result = []
        for t in transactions:
            voucher_url = t.voucher.url if t.voucher else None
            if voucher_url and not voucher_url.startswith('http') and request:
                voucher_url = request.build_absolute_uri(voucher_url)
            result.append({
                'id': t.id,
                'payment_method': t.payment_method,
                'mount': str(t.mount),
                'voucher': voucher_url,
                'payment_date': t.payment_date,
                'created_at': t.created_at,
                'is_validated': ('transaction', t.id) in validations,  # 👈
            })
        return result

    def get_enrollments(self, obj):
        request = self.context.get('request')
        validations = self.context.get('validations', set())  # 👈
        enrollments = Enrollment.objects.filter(
            participant=obj,
            is_active=True
        )
        result = []
        for e in enrollments:
            archive_url = e.archive.url if e.archive else None
            if archive_url and not archive_url.startswith('http') and request:
                archive_url = request.build_absolute_uri(archive_url)
            result.append({
                'id': e.id,
                'type': e.type,
                'archive': archive_url,
                'is_validated': ('enrollment', e.id) in validations,  # 👈
            })
        return result
    
    def get_is_validated(self, obj):
        validations = self.context.get('validations', set())  # 👈
        registration_id = obj.registration.id if obj.registration else None
        if not registration_id:
            return False
        return ('registration', registration_id) in validations
    

