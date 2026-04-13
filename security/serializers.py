from .models import PersonalData, User, Validation, EmailLog
from django.contrib.auth.models import Group
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Datos básicos
        token['user_id'] = user.id
        token['username'] = user.username
        token['email'] = user.email

        # Roles
        token['is_superuser'] = user.is_superuser 
        token['is_staff'] = user.is_staff  

        # Datos personales
        if user.personal_data_id:
            token['first_name'] = user.personal_data_id.first_name
            token['paternal_surname'] = user.personal_data_id.paternal_surname

        return token


class PersonalDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonalData
        fields = '__all__'

    def validate_dni(self, value):
        if PersonalData.objects.filter(dni=value).exists():
            raise serializers.ValidationError("El DNI ya está registrado")
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password',
            'is_staff', 'is_superuser', 'is_active',
            'date_joined', 'personal_data_id'
        ]
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
        'password': {'write_only': True}
    }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)  # mejor que make_password
        user.save()
        return user


class GroupSerializer(serializers.ModelSerializer):
    """Serializer para grupos"""
    
    class Meta:
        model = Group
        fields = ['id', 'name']


class UserPermissionsSerializer(serializers.ModelSerializer):
    personal_data = PersonalDataSerializer(source='personal_data_id', read_only=True)
    groups = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_staff', 'is_superuser', 
            'is_active', 'date_joined', 'personal_data', 
            'groups', 'permissions'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def get_groups(self, obj):
        """Obtener grupos del usuario"""
        return [{'id': g.id, 'name': g.name} for g in obj.groups.all()]
    
    def get_permissions(self, obj):
        """Obtener TODOS los permisos (directos + grupos)"""
        if obj.is_superuser:
            return ['*']  # Superuser tiene todos los permisos
        
        # Obtener permisos de Django (formato: app_label.codename)
        perms = obj.get_all_permissions()
        
        return list(perms)


class ValidationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Validation
        fields = '__all__'


class ValidationDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Validation
        fields = '__all__'


class EmailLogSerializer(serializers.ModelSerializer):
    participant_name = serializers.SerializerMethodField()
    participant_email = serializers.SerializerMethodField()
    email_type_display = serializers.CharField(
        source='get_email_type_display', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )

    class Meta:
        model = EmailLog
        fields = [
            'id',
            'participant',
            'participant_name',
            'participant_email',
            'subject',
            'email_type',
            'email_type_display',
            'status',
            'status_display',
            'error_message',
            'sent_at',
            'created_at',
        ]

    def get_participant_name(self, obj):
        p = obj.participant
        return f"{p.first_name} {p.paternal_surname} {p.maternal_surname}"

    def get_participant_email(self, obj):
        return obj.participant.email


# PUBLIC REGISTER

class UserRegisterSerializer(serializers.ModelSerializer):
    personal_data = PersonalDataSerializer()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password',
            'personal_data'
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("El email ya está registrado")
        return value

    @transaction.atomic
    def create(self, validated_data):
        personal_data_data = validated_data.pop('personal_data')

        # 1. Crear datos personales
        personal_data = PersonalData.objects.create(**personal_data_data)

        # 2. Crear usuario
        password = validated_data.pop('password')
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
        )

        # 🔐 FORZAR seguridad
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True

        user.personal_data_id = personal_data
        user.set_password(password)
        user.save()

        return user
    