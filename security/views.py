from security.services.mailtrap_service import check_mailtrap_suppression

from .models import PersonalData, User, Validation
from rest_framework.views import APIView
from .serializers import (
    PersonalDataSerializer, 
    UserSerializer,
    UserPermissionsSerializer,
    UserRegisterSerializer,
    ValidationSerializer,
    ValidationDetailSerializer
)
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status

from .models import EmailLog
from django.utils import timezone

from .services.email_service import send_welcome_email

# Create your views here.

class PersonalDataViewSet(viewsets.ModelViewSet):
    queryset = PersonalData.objects.all()
    permission_classes = [
        permissions.IsAdminUser
    ]
    serializer_class = PersonalDataSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [
        permissions.IsAdminUser
    ]
    serializer_class = UserSerializer
    
    # ============================================
    # ENDPOINTS DE PERMISOS
    # ============================================
    
    def get_permissions(self):
        permission_map = {
            'current_user': [permissions.IsAuthenticated],
            'user_permissions': [permissions.IsAuthenticated],
            'user_groups': [permissions.IsAuthenticated],
        }

        return [perm() for perm in permission_map.get(self.action, [permissions.IsAdminUser])]
    
    @action(detail=False, methods=['get'], url_path='current')
    def current_user(self, request):
        """
        Obtener información completa del usuario autenticado con permisos
        GET /api/security/user/current/
        Requiere: Bearer Token
        """
        
        serializer = UserPermissionsSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def user_permissions(self, request):
        """
        Obtener solo los permisos del usuario autenticado
        GET /api/security/user/permissions/
        Requiere: Bearer Token
        """
        # Verificar que el usuario esté autenticado
        
        user = request.user
        
        if user.is_superuser:
            permissions_list = ['*']
        else:
            permissions_list = list(user.get_all_permissions())
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'permissions': permissions_list,
            'permissions_count': len(permissions_list) if permissions_list != ['*'] else 'all'
        })
    
    @action(detail=False, methods=['get'], url_path='groups')
    def user_groups(self, request):
        """
        Obtener grupos del usuario autenticado
        GET /api/security/user/groups/
        Requiere: Bearer Token
        """
    
        user = request.user
        groups = user.groups.all()
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'groups': [
                {
                    'id': group.id,
                    'name': group.name,
                    'permissions_count': group.permissions.count()
                }
                for group in groups
            ],
            'groups_count': groups.count()
        })


class ValidationAdminViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def _toggle(self, request, model_name, register_id):
        user = request.user
        existing = Validation.objects.filter(
            model=model_name,
            register_id=register_id,
        ).first()

        if existing:
            existing.delete()
            return Response({'validated': False}, status=status.HTTP_200_OK)
        else:
            Validation.objects.create(
                user=user,
                model=model_name,
                register_id=register_id,
                validated=True,
            )

            # 👈 Enviar email solo si es validación de registration
            if model_name == 'registration':
                from participant.models import Participant

                participant = None
                try:
                    participant = Participant.objects.select_related(
                        'registration__quota_type',
                        'registration__pre_sale',
                    ).get(
                        registration_id=register_id,
                        is_active=True
                    )

                    # ✅ Verificar si el envío de correos está habilitado
                    if settings.AVAILABLE_EMAILS:
                        import threading
                        hilo = threading.Thread(target=send_welcome_email, args=(participant,))
                        hilo.daemon = True
                        hilo.start()
                        email_status = 'sent'
                        error_message = None
                    else:
                        email_status = 'disabled'
                        error_message = 'El envío de correos está deshabilitado por configuración.'

                except Exception as e:
                    email_status = 'failed'
                    error_message = str(e)

                # 📌 Verificar suppressions en Mailtrap
                if participant and participant.email and email_status == 'sent':
                    suppression = check_mailtrap_suppression(participant.email)

                    if suppression:
                        email_status = 'bounced'
                        esp_response = suppression.get("message_esp_response")
                        error_message = esp_response
                    else:
                        email_status = 'sent'

                # Registrar el resultado en EmailLog si existe el participante
                if participant:
                    EmailLog.objects.create(
                        participant=participant,
                        subject='¡Bienvenido al XXXII CONAEA Tarapoto 2026!',
                        email_type='validation',
                        status=email_status,
                        error_message=error_message,
                        sent_at=timezone.now() if email_status == 'sent' else None,
                    )

            return Response({'validated': True}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='enrollment/(?P<register_id>[0-9]+)')
    def enrollment(self, request, register_id=None):
        """
        POST /api/auth/validation/enrollment/{enrollment_id}/
        Valida o desvalida una ficha de matrícula.
        """
        return self._toggle(request, 'enrollment', int(register_id))

    @action(detail=False, methods=['post'], url_path='transaction/(?P<register_id>[0-9]+)')
    def transaction(self, request, register_id=None):
        """
        POST /api/auth/validation/transaction/{transaction_id}/
        Valida o desvalida una transacción.
        """
        return self._toggle(request, 'transaction', int(register_id))

    # @action(detail=False, methods=['post'], url_path='registration/(?P<participant_id>[0-9]+)')
    # def registration(self, request, participant_id=None):
    #     from participant.models import Participant, Enrollment
    #     from register.models import Transaction

    #     try:
    #         participant = Participant.objects.get(pk=participant_id, is_active=True)
    #     except Participant.DoesNotExist:
    #         return Response(
    #             {'detail': 'Participante no encontrado.'},
    #             status=status.HTTP_404_NOT_FOUND,
    #         )

    #     if not participant.registration_id:
    #         return Response(
    #             {'detail': 'El participante no tiene registro asociado.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # Verificar que todos los enrollments activos estén validados
    #     enrollment_ids = Enrollment.objects.filter(
    #         participant=participant,
    #         is_active=True,
    #     ).values_list('id', flat=True)

    #     validated_enrollments = Validation.objects.filter(
    #         model='enrollment',
    #         register_id__in=enrollment_ids,
    #     ).count()

    #     if validated_enrollments < len(enrollment_ids):
    #         return Response(
    #             {'detail': 'No todos los enrollments están validados.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # Verificar que todas las transactions activas estén validadas
    #     transaction_ids = Transaction.objects.filter(
    #         registration_id=participant.registration_id,
    #         is_active=True,
    #     ).values_list('id', flat=True)

    #     validated_transactions = Validation.objects.filter(
    #         model='transaction',
    #         register_id__in=transaction_ids,
    #     ).count()

    #     if validated_transactions < len(transaction_ids):
    #         return Response(
    #             {'detail': 'No todas las transacciones están validadas.'},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     return self._toggle(request, 'registration', participant.registration_id)

    @action(detail=False, methods=['post'], url_path='registration/(?P<participant_id>[0-9]+)')
    def registration(self, request, participant_id=None):
        from participant.models import Participant, Enrollment
        from register.models import Transaction

        try:
            participant = Participant.objects.select_related(
                'registration__quota_type'
            ).get(pk=participant_id, is_active=True)
        except Participant.DoesNotExist:
            return Response(
                {'detail': 'Participante no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not participant.registration_id:
            return Response(
                {'detail': 'El participante no tiene registro asociado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_general = participant.registration.quota_type.name == 'General'

        # ── Validar enrollments solo si NO es General ──────────────
        if not is_general:
            enrollment_ids = Enrollment.objects.filter(
                participant=participant,
                is_active=True,
            ).values_list('id', flat=True)

            validated_enrollments = Validation.objects.filter(
                model='enrollment',
                register_id__in=enrollment_ids,
            ).count()

            if validated_enrollments < len(enrollment_ids):
                return Response(
                    {'detail': 'No todos los enrollments están validados.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── Validar transactions (siempre) ─────────────────────────
        transaction_ids = Transaction.objects.filter(
            registration_id=participant.registration_id,
            is_active=True,
        ).values_list('id', flat=True)

        validated_transactions = Validation.objects.filter(
            model='transaction',
            register_id__in=transaction_ids,
        ).count()

        if validated_transactions < len(transaction_ids):
            return Response(
                {'detail': 'No todas las transacciones están validadas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self._toggle(request, 'registration', participant.registration_id)



# PUBLIC VIEW

class RegisterUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Usuario creado correctamente",
                "user_id": user.id
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ValidationViewSet(viewsets.ModelViewSet):
    queryset = Validation.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ValidationDetailSerializer
        return ValidationSerializer

    def get_queryset(self):
        queryset = Validation.objects.filter(is_active=True)
        model = self.request.query_params.get('model')
        register_id = self.request.query_params.get('register_id')
        if model:
            queryset = queryset.filter(model=model)
        if register_id:
            queryset = queryset.filter(register_id=register_id)
        return queryset

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'error': 'Contraseña actual y nueva son requeridas.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        if not user.check_password(current_password):
            return Response(
                {'error': 'La contraseña actual es incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if current_password == new_password:
            return Response(
                {'error': 'La nueva contraseña debe ser diferente a la actual.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {'message': 'Contraseña actualizada correctamente.'},
            status=status.HTTP_200_OK
        )