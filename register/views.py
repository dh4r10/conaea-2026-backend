from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import connection, transaction as db_transaction
from rest_framework.views import APIView, View
from .models import PreSale, QuotaType, AvailableSlot, Registration, Transaction, Refund, DynamicCode
from participant.models import Participant
from participant.models import Enrollment
from .serializers import (
    PreSaleSerializer,
    QuotaTypeSerializer,
    AvailableSlotSerializer,
    AvailableSlotDetailSerializer,
    RegistrationSerializer,
    RegistrationDetailSerializer,
    TransactionSerializer,
    TransactionDetailSerializer,
    RefundSerializer,
    DynamicCodeSerializer,
    DynamicCodeDetailSerializer
)
from participant.serializers import ParticipantValidationSerializer
from participant.models import PartnerUniversity, ParticipantSpecialCondition
from .pagination import StandardPagination

import random
import string

import json
import time
from django.http import StreamingHttpResponse


def generate_dynamic_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    digits = ''.join(random.choices(string.digits, k=2))
    return letters + digits


class PreSaleViewSet(viewsets.ModelViewSet):
    queryset = PreSale.objects.filter(is_active=True)
    serializer_class = PreSaleSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=['get'], url_path='slots')
    def slots(self, request, pk=None):
        """
        Obtener cupos disponibles de una preventa
        GET /api/register/pre-sale/{id}/slots/
        """
        pre_sale = self.get_object()
        slots = AvailableSlot.objects.filter(pre_sale=pre_sale, is_active=True)
        serializer = AvailableSlotDetailSerializer(slots, many=True)
        return Response(serializer.data)


class QuotaTypeViewSet(viewsets.ModelViewSet):
    queryset = QuotaType.objects.filter(is_active=True)
    serializer_class = QuotaTypeSerializer
    permission_classes = [permissions.AllowAny]


class AvailableSlotViewSet(viewsets.ModelViewSet):
    queryset = AvailableSlot.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):  # 👈
            return AvailableSlotDetailSerializer
        return AvailableSlotSerializer

    def get_queryset(self):
        queryset = AvailableSlot.objects.filter(is_active=True)
        pre_sale_id = self.request.query_params.get('pre_sale_id')
        quota_type_id = self.request.query_params.get('quota_type_id')
        if pre_sale_id:
            queryset = queryset.filter(pre_sale_id=pre_sale_id)
        if quota_type_id:
            queryset = queryset.filter(quota_type_id=quota_type_id)
        return queryset


class RegistrationViewSet(viewsets.ModelViewSet):
    queryset = Registration.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return RegistrationDetailSerializer
        return RegistrationSerializer

    def create(self, request, *args, **kwargs):
        """Validar cupos disponibles antes de crear el registro"""
        pre_sale_id = request.data.get('pre_sale')
        quota_type_id = request.data.get('quota_type')

        try:
            slot = AvailableSlot.objects.get(
                pre_sale_id=pre_sale_id,
                quota_type_id=quota_type_id,
                is_active=True
            )
        except AvailableSlot.DoesNotExist:
            return Response(
                {'error': 'No existe el cupo para esta preventa'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Contar inscritos actuales
        used = Registration.objects.filter(
            pre_sale_id=pre_sale_id,
            quota_type_id=quota_type_id,
            is_active=True
        ).count()

        if used >= slot.amount:
            return Response(
                {'error': 'No hay cupos disponibles'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='transactions')
    def transactions(self, request, pk=None):
        """
        Obtener transacciones de un registro
        GET /api/register/registration/{id}/transactions/
        """
        registration = self.get_object()
        transactions = Transaction.objects.filter(
            registration=registration,
            is_active=True
        )
        serializer = TransactionDetailSerializer(transactions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='balance')
    def balance(self, request, pk=None):
        """
        Obtener balance de pagos de un registro
        GET /api/register/registration/{id}/balance/
        """
        registration = self.get_object()
        serializer = RegistrationDetailSerializer(registration)
        return Response(serializer.data.get('balance'))


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TransactionDetailSerializer
        return TransactionSerializer

    def get_queryset(self):
        queryset = Transaction.objects.filter(is_active=True)
        registration_id = self.request.query_params.get('registration_id')
        if registration_id:
            queryset = queryset.filter(registration_id=registration_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        payment_method = request.data.get('payment_method', '').strip()
        valid_methods = ('yape', 'bcp', 'bbva')

        if payment_method not in valid_methods:
            return Response(
                {'error': f'Método de pago inválido. Opciones: {", ".join(valid_methods)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(is_active=True)


class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.filter(is_active=True)
    serializer_class = RefundSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Refund.objects.filter(is_active=True)
        transaction_id = self.request.query_params.get('transaction_id')
        if transaction_id:
            queryset = queryset.filter(transaction_id=transaction_id)
        return queryset
    

class DynamicCodeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return DynamicCodeDetailSerializer
        return DynamicCodeSerializer

    def get_queryset(self):
        queryset = DynamicCode.objects.filter(is_active=True).select_related('quota_type')
        status = self.request.query_params.get('status')
        quota_type_id = self.request.query_params.get('quota_type_id')
        if status:
            queryset = queryset.filter(status=status)
        if quota_type_id:
            queryset = queryset.filter(quota_type_id=quota_type_id)
        return queryset

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        Genera un código dinámico para el tipo de cuota "General"
        POST /api/register/dynamic-code/generate/
        """
        try:
            quota_type = QuotaType.objects.get(name='General', is_active=True)
        except QuotaType.DoesNotExist:
            return Response(
                {'error': 'El tipo de cuota "General" no existe.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generar código único
        max_attempts = 10
        for _ in range(max_attempts):
            code = generate_dynamic_code()
            if not DynamicCode.objects.filter(code=code).exists():
                break
        else:
            return Response(
                {'error': 'No se pudo generar un código único. Intenta nuevamente.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        dynamic_code = DynamicCode.objects.create(
            quota_type=quota_type,
            code=code,
            status='Disponible',
        )

        serializer = DynamicCodeDetailSerializer(dynamic_code)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# PUBLICOS     

class VerifyCodeView(APIView):
    """
    Verifica el código de inscripción según el tipo.

    Referido  → busca en partner_universities.code
    General   → busca en dynamic_codes.code con status='Disponible'

    POST /api/register/verify-code/
    Body: { "university_type": "Referido"|"General", "code": "AB123" }
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        university_type = request.data.get('university_type', '').strip()
        code = request.data.get('code', '').strip()

        if not university_type or not code:
            return Response(
                {'error': 'Los campos university_type y code son requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if university_type not in ('Referido', 'General'):
            return Response(
                {'error': 'university_type debe ser "Referido" o "General"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Caso Referido ──────────────────────────────────────────────
        if university_type == 'Referido':
            try:
                university = PartnerUniversity.objects.select_related(
                    'quota_type'
                ).get(code=code, is_active=True)
            except PartnerUniversity.DoesNotExist:
                return Response(
                    {'error': 'Código inválido'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Obtener monto de la preventa activa
            now = timezone.now()
            slot = AvailableSlot.objects.filter(
                pre_sale__start_date__lte=now,
                pre_sale__end_date__gte=now,
                pre_sale__is_active=True,
                quota_type=university.quota_type,
                is_active=True,
            ).select_related('pre_sale').first()

            return Response({
                'valid': True,
                'university_type': 'Referido',
                'cod_university': university.code,
                'university_name': university.name,
                'country': university.country,
                'region': university.region,
                'place': university.place,
                'quota_type_id': university.quota_type.id,
                'quota_type_name': university.quota_type.name,
                'currency': university.quota_type.currency,
                'mount': str(slot.mount) if slot else None,
            }, status=status.HTTP_200_OK)

        # ── Caso General ───────────────────────────────────────────────
        try:
            dynamic_code = DynamicCode.objects.select_related(
                'quota_type'
            ).get(code=code, is_active=True)
        except DynamicCode.DoesNotExist:
            return Response(
                {'error': 'Código inválido'},
                status=status.HTTP_404_NOT_FOUND
            )

        if dynamic_code.status != 'Disponible':
            return Response(
                {'error': 'Código usado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()
        slot = AvailableSlot.objects.filter(
            pre_sale__start_date__lte=now,
            pre_sale__end_date__gte=now,
            pre_sale__is_active=True,
            quota_type=dynamic_code.quota_type,
            is_active=True,
        ).select_related('pre_sale').first()

        return Response({
            'valid': True,
            'university_type': 'General',
            'quota_type_id': dynamic_code.quota_type.id,
            'quota_type_name': dynamic_code.quota_type.name,
            'currency': dynamic_code.quota_type.currency,
            'mount': str(slot.mount) if slot else None,
        }, status=status.HTTP_200_OK)


class InscriptionView(APIView):
    """
    Registra la inscripción completa de un participante.

    POST /api/register/inscription/
    Acepta multipart/form-data (por el archivo .pdf)

    Campos requeridos comunes:
        university_type, code, pre_sale_id (opcional si hay solo una activa),
        first_name, paternal_surname, maternal_surname, birthdate,
        identity_document, document_type, email, academic_cycle, archive

    Solo General:
        cod_country, cod_university

    Referido:
        cod_country puede venir como '---' o vacío (se guarda 0)

    Opcionales:
        discapacidad, alergia  (texto; se omiten si vacíos)
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @db_transaction.atomic
    def post(self, request):
        data = request.data
        university_type = data.get('university_type', '').strip()
        code = data.get('code', '').strip()

        # ── 1. Validar tipo ────────────────────────────────────────────
        if university_type not in ('Referido', 'General'):
            return Response(
                {'error': 'university_type debe ser "Referido" o "General"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 2. Resolver universidad / código dinámico ──────────────────
        university = None
        dynamic_code = None
        quota_type = None
        cod_university = None
        cod_country = None

        if university_type == 'Referido':
            try:
                university = PartnerUniversity.objects.select_related(
                    'quota_type'
                ).get(code=code, is_active=True)
            except PartnerUniversity.DoesNotExist:
                return Response(
                    {'error': 'Código de universidad referida no válido'},
                    status=status.HTTP_404_NOT_FOUND
                )
            quota_type = university.quota_type
            cod_university = university.code
            cod_country = 0  # valor por defecto para Referido

        else:  # General
            try:
                dynamic_code = DynamicCode.objects.select_related(
                    'quota_type'
                ).get(code=code, is_active=True)
            except DynamicCode.DoesNotExist:
                return Response(
                    {'error': 'Código dinámico no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )
            if dynamic_code.status != 'Disponible':
                return Response(
                    {'error': 'El código dinámico ya fue usado o no está disponible'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            quota_type = dynamic_code.quota_type
            cod_university = '0'   # 👈 fijo
            cod_country = 0        # 👈 fijo

        # ── 3. Validar formulario del participante ─────────────────────
        data = request.data.copy()
        for field in ('discapacidad', 'alergia'):
            if data.get(field, '').strip() == '-':
                data[field] = ''

        serializer = ParticipantValidationSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ── 4. Verificar archivos ───────────────────────────────────
        archive = None
        if university_type == 'Referido':
            archive = request.FILES.get('archive')
            if not archive:
                return Response(
                    {'error': 'La ficha de matrícula es requerida'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        photograph = request.FILES.get('photograph')  # 👈
        if not photograph:
            return Response(
                {'error': 'La fotografía es requerida'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 5. Obtener preventa activa ─────────────────────────────────
        now = timezone.now()
        try:
            pre_sale = PreSale.objects.get(
                start_date__lte=now,
                end_date__gte=now,
                is_active=True
            )
        except PreSale.DoesNotExist:
            return Response(
                {'error': 'No hay una preventa activa en este momento'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PreSale.MultipleObjectsReturned:
            return Response(
                {'error': 'Existe más de una preventa activa. Contacta al administrador'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # ── 6. Verificar cupos disponibles ────────────────────────────
        try:
            slot = AvailableSlot.objects.get(
                pre_sale=pre_sale,
                quota_type=quota_type,
                is_active=True
            )
        except AvailableSlot.DoesNotExist:
            return Response(
                {'error': 'No hay cupos configurados para esta categoría'},
                status=status.HTTP_400_BAD_REQUEST
            )

        used = Registration.objects.filter(
            pre_sale=pre_sale,
            quota_type=quota_type,
            is_active=True
        ).count()

        if used >= slot.amount:
            return Response(
                {'error': 'No hay cupos disponibles para esta categoría'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 7. Verificar duplicados ───────────────────────────────────
        identity_document = data.get('identity_document', '').strip()
        email = data.get('email', '').strip()

        if Participant.objects.filter(identity_document=identity_document, is_active=True).exists():
            return Response(
                {'identity_document': 'Ya existe un participante con este documento de identidad'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"Verificando email duplicado: {email}")

        if Participant.objects.filter(email=email, is_active=True).exists():
            return Response(
                {'email': 'Ya existe un participante con este correo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 8. Crear Registration ─────────────────────────────────────
        registration = Registration.objects.create(
            pre_sale=pre_sale,
            quota_type=quota_type,
        )

        # ── 9. Crear Participant ──────────────────────────────────────
        participant = Participant.objects.create(
            registration=registration,
            photograph=photograph,
            first_name=data.get('first_name', '').strip(),
            paternal_surname=data.get('paternal_surname', '').strip(),
            maternal_surname=data.get('maternal_surname', '').strip(),
            birthday=data.get('birthdate'),
            identity_document=identity_document,
            document_type=data.get('document_type', '').strip(),
            cellphone=serializer.validated_data.get('cellphone', ''),
            email=email,
            cod_country=cod_country,
            cod_university=cod_university,
            university_type=university_type,
            academic_cycle=data.get('academic_cycle', '0').strip() if university_type == 'Referido' else '0',
        )

        # ── 10. Crear Enrollment (ficha de matrícula) ─────────────────
        if archive:
            Enrollment.objects.create(
                participant=participant,
                type='matricula',
                archive=archive,
            )

        # ── 11. Registrar condiciones especiales (si vienen) ──────────
        discapacidad = data.get('discapacidad', '').strip()
        alergia = data.get('alergia', '').strip()

        if discapacidad:
            ParticipantSpecialCondition.objects.create(
                participant=participant,
                special_condition_id=1,  # Discapacidad
                description=discapacidad,
            )
        if alergia:
            ParticipantSpecialCondition.objects.create(
                participant=participant,
                special_condition_id=2,  # Alergia
                description=alergia,
            )

        # ── 12. Marcar código dinámico como Usado (solo General) ──────
        if dynamic_code:
            dynamic_code.status = 'Usado'
            dynamic_code.used_at = now
            dynamic_code.save(update_fields=['status', 'used_at'])

        return Response({
            'message': 'Inscripción registrada exitosamente',
            'registration_uuid': str(registration.uuid),
            'participant_id': participant.id,
        }, status=status.HTTP_201_CREATED)
    

SLOT_ORDER = ['Internacional', 'Nacional', 'General']

class AvailableSlotsRealTimeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        local_slot_id    = AvailableSlot.objects.filter(is_active=True, quota_type__name='Local').values_list('quota_type_id', flat=True).first()
        general_slot_id  = AvailableSlot.objects.filter(is_active=True, quota_type__name='General').values_list('quota_type_id', flat=True).first()
        nacional_slot_id = AvailableSlot.objects.filter(is_active=True, quota_type__name='Nacional').values_list('quota_type_id', flat=True).first()
        intl_slot_id     = AvailableSlot.objects.filter(is_active=True, quota_type__name='Internacional').values_list('quota_type_id', flat=True).first()

        local_codes    = PartnerUniversity.objects.filter(quota_type_id=local_slot_id).values_list('code', flat=True)
        nacional_codes = PartnerUniversity.objects.filter(quota_type_id=nacional_slot_id).values_list('code', flat=True)
        intl_codes     = PartnerUniversity.objects.filter(quota_type_id=intl_slot_id).values_list('code', flat=True)

        counts = Participant.objects.filter(
            registration__is_active=True
        ).aggregate(
            nacional=Count(
                Case(When(cod_university__in=nacional_codes, then=1), output_field=IntegerField())
            ),
            internacional=Count(
                Case(When(cod_university__in=intl_codes, then=1), output_field=IntegerField())
            ),
            local=Count(
                Case(When(cod_university__in=local_codes, then=1), output_field=IntegerField())
            ),
            general=Count(
                Case(When(registration__quota_type_id=general_slot_id, then=1), output_field=IntegerField())
            ),
        )

        slots = AvailableSlot.objects.filter(
            is_active=True
        ).select_related('quota_type')

        slot_map      = {slot.quota_type.name: slot for slot in slots}
        general_slot  = slot_map.get('General')

        shared_enrolleds = counts['local'] + counts['general']
        shared_amount    = general_slot.amount if general_slot else 0

        data = []
        for name in SLOT_ORDER:
            slot = slot_map.get(name)
            if not slot:
                continue

            if name == 'General':
                data.append({
                    'label': 'Local / General',
                    'amount': shared_amount,
                    'enrolleds': shared_enrolleds,
                })
            elif name == 'Nacional':
                data.append({
                    'label': name,
                    'amount': slot.amount,
                    'enrolleds': counts['nacional'],
                })
            elif name == 'Internacional':
                data.append({
                    'label': name,
                    'amount': slot.amount,
                    'enrolleds': counts['internacional'],
                })

        data.append({
            'label': 'Total',
            'amount': sum(s['amount'] for s in data),
            'enrolleds': sum(s['enrolleds'] for s in data),
            'highlight': True,
        })

        return Response(data)
    

# def get_slots_data():
#     slots     = AvailableSlot.objects.filter(is_active=True).select_related('quota_type')
#     slot_map  = {slot.quota_type.name: slot for slot in slots}

#     local_slot   = slot_map.get('Local')
#     general_slot = slot_map.get('General')

#     counts = Participant.objects.filter(
#         registration__is_active=True
#     ).aggregate(
#         nacional=Count(
#             Case(When(registration__quota_type_id=slot_map['Nacional'].quota_type_id, then=1), output_field=IntegerField())
#         ),
#         internacional=Count(
#             Case(When(registration__quota_type_id=slot_map['Internacional'].quota_type_id, then=1), output_field=IntegerField())
#         ),
#         local=Count(
#             Case(When(registration__quota_type_id=local_slot.quota_type_id, then=1), output_field=IntegerField())
#         ),
#         general=Count(
#             Case(When(registration__quota_type_id=general_slot.quota_type_id, then=1), output_field=IntegerField())
#         ),
#     )

#     shared_enrolleds = counts['local'] + counts['general']
#     shared_amount    = general_slot.amount if general_slot else 0

#     data = []
#     for name in SLOT_ORDER:
#         slot = slot_map.get(name)
#         if not slot:
#             continue

#         if name == 'General':
#             data.append({
#                 'label': 'Local / General',
#                 'amount': shared_amount,
#                 'enrolleds': shared_enrolleds,
#             })
#         elif name == 'Nacional':
#             data.append({
#                 'label': name,
#                 'amount': slot.amount,
#                 'enrolleds': counts['nacional'],
#             })
#         elif name == 'Internacional':
#             data.append({
#                 'label': name,
#                 'amount': slot.amount,
#                 'enrolleds': counts['internacional'],
#             })

#     data.append({
#         'label': 'Total',
#         'amount': sum(s['amount'] for s in data),
#         'enrolleds': sum(s['enrolleds'] for s in data),
#         'highlight': True,
#     })

#     return data


def get_slots_data():
    with connection.cursor() as cursor:
        cursor.execute('SELECT get_slots_data()')
        row = cursor.fetchone()
    return row[0]


class AvailableSlotsSSEView(View):

    def get(self, request):
        def event_stream():
            while True:
                try:
                    data = get_slots_data()
                    yield f"data: {json.dumps(data)}\n\n"
                    time.sleep(10)
                except GeneratorExit:
                    break

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
