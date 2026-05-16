from security.services.mailtrap_service import check_mailtrap_suppression

from .models import PersonalData, User, Validation
from rest_framework.views import APIView
from .serializers import (
    PersonalDataSerializer,
    UserSerializer,
    UserPermissionsSerializer,
    UserRegisterSerializer,
    ValidationSerializer,
    ValidationDetailSerializer,
    EmailLogSerializer,
)
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status

from .models import EmailLog
from django.utils import timezone
from participant.pagination import StandardPagination

from .services.email_service import send_welcome_email

import json
import time
from django.http import StreamingHttpResponse, HttpResponse
from django.views import View

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

                        def send_and_log(p):
                            try:
                                send_welcome_email(p)
                                suppression = check_mailtrap_suppression(p.email)
                                if suppression:
                                    suppression_type = suppression.get('type', 'suppression')
                                    esp_response = suppression.get('message_esp_response') or ''
                                    log_status = 'bounced'
                                    log_error = f"{suppression_type} — {esp_response}".strip(' —')
                                    log_sent_at = None
                                else:
                                    log_status = 'sent'
                                    log_error = None
                                    log_sent_at = timezone.now()
                            except Exception as exc:
                                log_status = 'failed'
                                log_error = str(exc)
                                log_sent_at = None

                            EmailLog.objects.create(
                                participant=p,
                                subject='¡Bienvenido al XXXII CONAEA Tarapoto 2026!',
                                email_type='validation',
                                status=log_status,
                                error_message=log_error,
                                sent_at=log_sent_at,
                            )

                        hilo = threading.Thread(target=send_and_log, args=(participant,))
                        hilo.daemon = True
                        hilo.start()
                    else:
                        EmailLog.objects.create(
                            participant=participant,
                            subject='¡Bienvenido al XXXII CONAEA Tarapoto 2026!',
                            email_type='validation',
                            status='disabled',
                            error_message='El envío de correos está deshabilitado por configuración.',
                            sent_at=None,
                        )

                except Exception as e:
                    if participant:
                        EmailLog.objects.create(
                            participant=participant,
                            subject='¡Bienvenido al XXXII CONAEA Tarapoto 2026!',
                            email_type='validation',
                            status='failed',
                            error_message=str(e),
                            sent_at=None,
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

class EmailLogListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        participant_id = request.query_params.get('participant_id')
        if not participant_id:
            return Response(
                {'error': 'El parámetro participant_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logs = EmailLog.objects.filter(participant_id=participant_id)

        status_filter = request.query_params.get('status')
        if status_filter:
            logs = logs.filter(status=status_filter)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(logs, request)
        serializer = EmailLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ResendEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from participant.models import Participant

        participant_id = request.data.get('participant_id')
        if not participant_id:
            return Response(
                {'detail': 'El campo participant_id es requerido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            participant = Participant.objects.select_related(
                'registration__quota_type',
                'registration__pre_sale',
            ).get(pk=participant_id, is_active=True)
        except Participant.DoesNotExist:
            return Response(
                {'detail': 'Participante no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not participant.registration_id:
            return Response(
                {'detail': 'El participante no tiene una inscripción asociada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not settings.AVAILABLE_EMAILS:
            return Response(
                {'detail': 'El envío de correos está deshabilitado por configuración.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import threading

        def send_and_log(p):
            try:
                send_welcome_email(p)
                suppression = check_mailtrap_suppression(p.email)
                if suppression:
                    suppression_type = suppression.get('type', 'suppression')
                    esp_response = suppression.get('message_esp_response') or ''
                    log_status = 'bounced'
                    log_error = f"{suppression_type} — {esp_response}".strip(' —')
                    log_sent_at = None
                else:
                    log_status = 'sent'
                    log_error = None
                    log_sent_at = timezone.now()
            except Exception as exc:
                log_status = 'failed'
                log_error = str(exc)
                log_sent_at = None

            EmailLog.objects.create(
                participant=p,
                subject='¡Bienvenido al XXXII CONAEA Tarapoto 2026!',
                email_type='validation',
                status=log_status,
                error_message=log_error,
                sent_at=log_sent_at,
            )

        hilo = threading.Thread(target=send_and_log, args=(participant,))
        hilo.daemon = True
        hilo.start()

        return Response({'detail': 'Email reenviado correctamente.'})


class EmailStatusSSEView(View):
    """
    GET /api/security/email-status/sse/?participant_id=X
    Mantiene la conexión abierta y emite el estado del último EmailLog
    del participante en cuanto el hilo de envío lo escribe.
    Cierra la conexión al recibir un estado definitivo (sent, bounced, failed, disabled).
    """
    TERMINAL_STATUSES = {'sent', 'bounced', 'failed', 'disabled'}
    TIMEOUT_SECONDS = 60

    def get(self, request):
        participant_id = request.GET.get('participant_id', '').strip()
        if not participant_id:
            return HttpResponse('participant_id requerido', status=400)

        # ID del último log ANTES de que llegue la solicitud, para detectar uno nuevo
        last_log = (
            EmailLog.objects.filter(participant_id=participant_id)
            .order_by('-created_at')
            .values('id', 'status')
            .first()
        )
        seen_id = last_log['id'] if last_log else None

        def event_stream():
            deadline = time.time() + self.TIMEOUT_SECONDS
            while time.time() < deadline:
                try:
                    new_log = (
                        EmailLog.objects.filter(participant_id=participant_id)
                        .order_by('-created_at')
                        .values('id', 'status', 'error_message')
                        .first()
                    )
                    if new_log and new_log['id'] != seen_id:
                        yield f"data: {json.dumps({'status': new_log['status'], 'error': new_log['error_message']})}\n\n"
                        if new_log['status'] in self.TERMINAL_STATUSES:
                            return
                    time.sleep(1)
                except GeneratorExit:
                    return
                except Exception:
                    return
            yield f"data: {json.dumps({'status': 'timeout'})}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate
        from participant.models import Participant, PartnerUniversity, Delegate
        from register.models import AvailableSlot, DynamicCode, PreSale, Registration, IndividualCup
        from activity.models import Speaker, Day, Activity

        # ── Participants ──────────────────────────────────────────
        total_p = Participant.objects.filter(is_active=True).count()
        validated_ids = Validation.objects.filter(model='registration').values_list('register_id', flat=True)
        validated_p = Participant.objects.filter(is_active=True, registration_id__in=validated_ids).count()

        by_date = list(
            Registration.objects.filter(is_active=True)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        by_quota_type = list(
            Registration.objects.filter(is_active=True)
            .values('quota_type__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        by_pre_sale_participants = list(
            Registration.objects.filter(is_active=True)
            .values('pre_sale__name')
            .annotate(count=Count('id'))
            .order_by('pre_sale__id')
        )

        # ── Slots ─────────────────────────────────────────────────
        slot_qs = AvailableSlot.objects.filter(is_active=True)
        total_slots = slot_qs.aggregate(total=Sum('amount'))['total'] or 0
        slots_reserved = IndividualCup.objects.filter(is_active=True).aggregate(total=Sum('currency'))['total'] or 0

        # ── Codes ─────────────────────────────────────────────────
        total_codes = DynamicCode.objects.filter(is_active=True).count()
        available_codes = DynamicCode.objects.filter(is_active=True, status='Disponible').count()

        # ── Top universities ──────────────────────────────────────
        top_uni_qs = list(
            Participant.objects.filter(is_active=True)
            .values('cod_university')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        top_codes = [r['cod_university'] for r in top_uni_qs]
        uni_map = {u.code: u for u in PartnerUniversity.objects.filter(code__in=top_codes)}
        top_universities = [
            {
                'name': uni_map[r['cod_university']].name if r['cod_university'] in uni_map else r['cod_university'],
                'abbreviation': uni_map[r['cod_university']].abbreviation if r['cod_university'] in uni_map else '',
                'count': r['count'],
            }
            for r in top_uni_qs
        ]

        # ── Delegates ─────────────────────────────────────────────
        total_delegates = Delegate.objects.filter(is_active=True).count()

        ps_uni_codes = {}
        for row in (
            Participant.objects.filter(is_active=True)
            .values('cod_university', 'registration__pre_sale__name')
            .distinct()
        ):
            ps_name = row['registration__pre_sale__name']
            ps_uni_codes.setdefault(ps_name, set()).add(row['cod_university'])

        all_uni_codes = set().union(*ps_uni_codes.values()) if ps_uni_codes else set()
        del_count_by_code = {}
        if all_uni_codes:
            for row in (
                Delegate.objects.filter(is_active=True, partner_university__code__in=all_uni_codes)
                .values('partner_university__code')
                .annotate(cnt=Count('id'))
            ):
                del_count_by_code[row['partner_university__code']] = row['cnt']

        delegates_by_pre_sale = [
            {'pre_sale': ps_name, 'count': sum(del_count_by_code.get(c, 0) for c in codes)}
            for ps_name, codes in ps_uni_codes.items()
        ]

        # ── Universities ──────────────────────────────────────────
        total_universities = PartnerUniversity.objects.filter(is_active=True).count()
        active_uni_codes = Participant.objects.filter(is_active=True).values('cod_university').distinct()
        with_participants = PartnerUniversity.objects.filter(is_active=True, code__in=active_uni_codes).count()

        # ── Activities ────────────────────────────────────────────
        total_activities = Activity.objects.filter(is_active=True).count()
        activities_by_day = list(
            Activity.objects.filter(is_active=True)
            .values('day__title')
            .annotate(count=Count('id'))
            .order_by('day__date')
        )

        # ── Active pre_sale ───────────────────────────────────────
        active_pre_sale = PreSale.objects.filter(is_active=True).first()
        pre_sale_data = None
        if active_pre_sale:
            used_by_qt = dict(
                Registration.objects.filter(is_active=True, pre_sale=active_pre_sale)
                .values('quota_type_id')
                .annotate(cnt=Count('id'))
                .values_list('quota_type_id', 'cnt')
            )
            reserved_by_qt = {}
            if active_pre_sale.booking_mode:
                for row in (
                    IndividualCup.objects.filter(is_active=True, pre_sale=active_pre_sale)
                    .values('partner_university__quota_type_id')
                    .annotate(total=Sum('currency'))
                ):
                    reserved_by_qt[row['partner_university__quota_type_id']] = row['total']

            slots = []
            for slot in (
                AvailableSlot.objects.filter(pre_sale=active_pre_sale, is_active=True)
                .values('quota_type__name', 'quota_type_id', 'amount')
                .order_by('id')
            ):
                qt_id = slot['quota_type_id']
                slots.append({
                    'quota_type__name': slot['quota_type__name'],
                    'amount': slot['amount'],
                    'used': used_by_qt.get(qt_id, 0),
                    'reserved': reserved_by_qt.get(qt_id, 0) if active_pre_sale.booking_mode else 0,
                })

            pre_sale_data = {
                'name': active_pre_sale.name,
                'start_date': active_pre_sale.start_date,
                'end_date': active_pre_sale.end_date,
                'booking_mode': active_pre_sale.booking_mode,
                'slots': slots,
            }

        return Response({
            'participants': {
                'total': total_p,
                'validated': validated_p,
                'pending': total_p - validated_p,
                'by_date': [{'date': str(r['date']), 'count': r['count']} for r in by_date],
                'by_quota_type': [{'quota_type': r['quota_type__name'], 'count': r['count']} for r in by_quota_type],
                'by_pre_sale': [{'pre_sale': r['pre_sale__name'], 'count': r['count']} for r in by_pre_sale_participants],
            },
            'slots': {
                'total': total_slots,
                'used': total_p,
                'reserved': slots_reserved,
                'categories': slot_qs.count(),
            },
            'speakers': Speaker.objects.filter(is_active=True).count(),
            'days': Day.objects.filter(is_active=True).count(),
            'codes': {
                'total': total_codes,
                'available': available_codes,
                'used': total_codes - available_codes,
            },
            'delegates': {
                'total': total_delegates,
                'by_pre_sale': delegates_by_pre_sale,
            },
            'universities': {
                'total': total_universities,
                'with_participants': with_participants,
            },
            'activities': {
                'total': total_activities,
                'by_day': [{'day': r['day__title'], 'count': r['count']} for r in activities_by_day],
            },
            'top_universities': top_universities,
            'active_pre_sale': pre_sale_data,
        })


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