import logging

from django.utils import timezone
from django.db.models import Count, Case, When, IntegerField
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import connection, transaction as db_transaction, IntegrityError
from rest_framework.views import APIView, View

from .models import PreSale, QuotaType, AvailableSlot, Registration, Transaction, Refund, DynamicCode, IndividualCup
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
    DynamicCodeDetailSerializer,
    IndividualCupSerializer,
    IndividualCupDetailSerializer,
)
from participant.serializers import ParticipantValidationSerializer
from participant.models import PartnerUniversity, ParticipantSpecialCondition
from .pagination import StandardPagination

import random
import string

import json
import time
from django.http import StreamingHttpResponse

logger = logging.getLogger(__name__)


def generate_dynamic_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    digits = ''.join(random.choices(string.digits, k=2))
    return letters + digits


def get_pre_sales_with_default():
    pre_sales_qs = list(PreSale.objects.filter(is_active=True).values('id', 'name', 'start_date', 'end_date'))
    now = timezone.now()
    in_range = [p for p in pre_sales_qs if p['start_date'] <= now <= p['end_date']]
    if in_range:
        default_id = in_range[0]['id']
    else:
        past = [p for p in pre_sales_qs if p['start_date'] < now]
        default_id = max(past, key=lambda p: p['start_date'])['id'] if past else None
    return [
        {'id': p['id'], 'name': p['name'], 'is_default': p['id'] == default_id}
        for p in pre_sales_qs
    ]


class PreSaleViewSet(viewsets.ModelViewSet):
    queryset = PreSale.objects.filter(is_active=True)
    serializer_class = PreSaleSerializer
    permission_classes = [permissions.AllowAny]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            slots_count = AvailableSlot.objects.filter(pre_sale=instance, is_active=True).count()
            if slots_count:
                return Response(
                    {'detail': f'No se puede desactivar la preventa porque tiene {slots_count} cupo{"s" if slots_count != 1 else ""} asociado{"s" if slots_count != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        was_booking = instance.booking_mode
        response = super().update(request, *args, **kwargs)
        instance.refresh_from_db(fields=['booking_mode'])
        if was_booking and not instance.booking_mode:
            IndividualCup.objects.filter(pre_sale=instance, is_active=True).update(is_active=False)
        return response

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

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            slots_count = AvailableSlot.objects.filter(quota_type=instance, is_active=True).count()
            if slots_count:
                return Response(
                    {'detail': f'No se puede desactivar el tipo de cuota porque tiene {slots_count} cupo{"s" if slots_count != 1 else ""} asociado{"s" if slots_count != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return super().update(request, *args, **kwargs)


class AvailableSlotViewSet(viewsets.ModelViewSet):
    queryset = AvailableSlot.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return AvailableSlotDetailSerializer
        return AvailableSlotSerializer

    def get_queryset(self):
        from django.db.models import OuterRef, Subquery, IntegerField, Value, Sum
        from django.db.models.functions import Coalesce
        reserved_subquery = IndividualCup.objects.filter(
            pre_sale=OuterRef('pre_sale'),
            partner_university__quota_type=OuterRef('quota_type'),
            is_active=True,
        ).values('pre_sale').annotate(total=Sum('currency')).values('total')
        queryset = AvailableSlot.objects.filter(is_active=True).annotate(
            reserved=Coalesce(Subquery(reserved_subquery, output_field=IntegerField()), Value(0))
        )
        pre_sale_id = self.request.query_params.get('pre_sale_id')
        quota_type_id = self.request.query_params.get('quota_type_id')
        if pre_sale_id:
            queryset = queryset.filter(pre_sale_id=pre_sale_id)
        if quota_type_id:
            queryset = queryset.filter(quota_type_id=quota_type_id)
        return queryset

    def update(self, request, *args, **kwargs):
        from django.db.models import Sum
        instance = self.get_object()

        new_is_active = request.data.get('is_active')
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            enrolled = Registration.objects.filter(
                pre_sale=instance.pre_sale,
                quota_type=instance.quota_type,
                is_active=True,
            ).count()
            if enrolled:
                return Response(
                    {'detail': f'No se puede desactivar el cupo porque hay {enrolled} participante{"s" if enrolled != 1 else ""} inscrito{"s" if enrolled != 1 else ""}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        new_amount = request.data.get('amount')

        if new_amount is not None:
            try:
                new_amount = int(new_amount)
            except (ValueError, TypeError):
                return Response(
                    {'amount': 'Debe ser un número entero.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            booking_mode = instance.pre_sale.booking_mode

            if booking_mode:
                total_reserved = IndividualCup.objects.filter(
                    pre_sale=instance.pre_sale,
                    partner_university__quota_type=instance.quota_type,
                    is_active=True,
                ).aggregate(total=Sum('currency'))['total'] or 0

                if new_amount < total_reserved:
                    return Response(
                        {'amount': f'La cantidad no puede ser menor a los cupos ya reservados por universidades ({total_reserved}).'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            used_total = Registration.objects.filter(
                pre_sale=instance.pre_sale,
                quota_type=instance.quota_type,
                is_active=True,
            ).count()

            if new_amount < used_total:
                return Response(
                    {'amount': f'La cantidad no puede ser menor al total de participantes ya inscritos ({used_total}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if booking_mode:
                reserved_codes = list(
                    IndividualCup.objects.filter(
                        pre_sale=instance.pre_sale,
                        partner_university__quota_type=instance.quota_type,
                        is_active=True,
                    ).values_list('partner_university__code', flat=True)
                )
                used_reserved = Participant.objects.filter(
                    cod_university__in=reserved_codes,
                    is_active=True,
                ).count() if reserved_codes else 0

                free_slots = new_amount - total_reserved
                non_reserved_enrollees = used_total - used_reserved
                if free_slots < non_reserved_enrollees:
                    return Response(
                        {'amount': f'Los cupos libres resultantes ({free_slots}) no alcanzan para los inscritos fuera de reserva ({non_reserved_enrollees}).'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        return super().update(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        from collections import defaultdict
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = list(serializer.data)

        pre_sale_ids = {slot.pre_sale_id for slot in queryset}

        booking_mode_map = {
            p['id']: p['booking_mode']
            for p in PreSale.objects.filter(id__in=pre_sale_ids).values('id', 'booking_mode')
        }

        # used_total: inscritos por (pre_sale, quota_type)
        reg_counts = (
            Registration.objects.filter(pre_sale_id__in=pre_sale_ids, is_active=True)
            .values('pre_sale_id', 'quota_type_id')
            .annotate(count=Count('id'))
        )
        used_total_map = {(r['pre_sale_id'], r['quota_type_id']): r['count'] for r in reg_counts}

        # used_reserved: solo relevante cuando booking_mode=True
        booking_pre_sale_ids = {pid for pid, bm in booking_mode_map.items() if bm}
        code_to_keys = defaultdict(list)
        if booking_pre_sale_ids:
            cups = IndividualCup.objects.filter(
                pre_sale_id__in=booking_pre_sale_ids,
                is_active=True,
            ).values('pre_sale_id', 'partner_university__quota_type_id', 'partner_university__code')
            for cup in cups:
                key = (cup['pre_sale_id'], cup['partner_university__quota_type_id'])
                code_to_keys[cup['partner_university__code']].append(key)

        used_reserved_map = defaultdict(int)
        if code_to_keys:
            participant_counts = (
                Participant.objects.filter(cod_university__in=code_to_keys.keys(), is_active=True)
                .values('cod_university')
                .annotate(count=Count('id'))
            )
            for pc in participant_counts:
                for key in code_to_keys[pc['cod_university']]:
                    used_reserved_map[key] += pc['count']

        for item, slot in zip(data, queryset):
            key = (slot.pre_sale_id, slot.quota_type_id)
            booking = booking_mode_map.get(slot.pre_sale_id, False)
            item['used_total'] = used_total_map.get(key, 0)
            item['used_reserved'] = used_reserved_map.get(key, 0) if booking else 0
            if not booking:
                item['reserved'] = 0

        return Response({
            'pre_sales': get_pre_sales_with_default(),
            'results': data,
        })


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

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT verify_registration_code(%s, %s)',
                [university_type, code]
            )
            result = json.loads(cursor.fetchone()[0])

        http_status = result.pop('http_status', 200)
        if 'error' in result:
            return Response(result, status=http_status)
        return Response(result, status=status.HTTP_200_OK)


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
        # request.data.copy() falla cuando hay TemporaryUploadedFile (no pickleable).
        # Se construye un dict plano con POST + FILES para evitar deepcopy del QueryDict.
        # dict.update(MultiValueDict) usa la ruta rápida de CPython que lee listas internas
        # en vez de llamar __getitem__, por eso se usa .items() que sí devuelve el archivo.
        serializer_data = request.POST.dict()
        for k, v in request.FILES.items():
            serializer_data[k] = v
        for field in ('discapacidad', 'alergia'):
            if serializer_data.get(field, '').strip() == '-':
                serializer_data[field] = ''

        serializer = ParticipantValidationSerializer(data=serializer_data)
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

        # ── 6.5. Verificar cupo individual por universidad (booking_mode) ─
        if pre_sale.booking_mode:
            if university_type == 'General':
                return Response(
                    {'error': 'Las inscripciones de tipo General no están disponibles en este momento'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                individual_cup = IndividualCup.objects.get(
                    pre_sale=pre_sale,
                    partner_university=university,
                    is_active=True,
                )
                used_by_university = Participant.objects.filter(
                    cod_university=cod_university,
                    is_active=True,
                ).count()
                if used_by_university >= individual_cup.currency:
                    return Response(
                        {'error': 'Cupos agotados'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except IndividualCup.DoesNotExist:
                return Response(
                    {'error': 'Tu universidad no tiene cupos registrados en esta preventa'},
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
        
        logger.info("Verificando email duplicado: %s", email)

        if Participant.objects.filter(email=email, is_active=True).exists():
            return Response(
                {'email': 'Ya existe un participante con este correo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 8. Crear Registration ─────────────────────────────────────
        try:
            registration = Registration.objects.create(
                pre_sale=pre_sale,
                quota_type=quota_type,
            )
        except Exception as exc:
            logger.error("Error al crear Registration pre_sale=%s quota_type=%s: %s", pre_sale.id, quota_type.id, exc, exc_info=True)
            raise

        # ── 9. Crear Participant ──────────────────────────────────────
        # Savepoint para poder capturar IntegrityError (race condition en duplicados)
        # sin abortar la transacción completa.
        cellphone = serializer.validated_data.get('cellphone') or data.get('cellphone', '').strip()
        sid = db_transaction.savepoint()
        try:
            participant = Participant.objects.create(
                registration=registration,
                photograph=photograph,
                first_name=data.get('first_name', '').strip(),
                paternal_surname=data.get('paternal_surname', '').strip(),
                maternal_surname=data.get('maternal_surname', '').strip(),
                birthday=data.get('birthdate'),
                identity_document=identity_document,
                document_type=data.get('document_type', '').strip(),
                cellphone=cellphone,
                email=email,
                cod_country=cod_country,
                cod_university=cod_university,
                university_type=university_type,
                academic_cycle=data.get('academic_cycle', '0').strip() if university_type == 'Referido' else '0',
            )
            db_transaction.savepoint_commit(sid)
        except IntegrityError as exc:
            db_transaction.savepoint_rollback(sid)
            logger.error("IntegrityError al crear Participant (email=%s, doc=%s): %s", email, identity_document, exc, exc_info=True)
            return Response(
                {'error': 'Ya existe un participante con ese documento o correo electrónico.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            logger.error("Error al crear Participant (email=%s): %s", email, exc, exc_info=True)
            raise

        logger.info("Participant creado exitosamente: id=%s email=%s", participant.id, email)

        # ── 10. Crear Enrollment (ficha de matrícula) ─────────────────
        if archive:
            _last_exc = None
            for _attempt in range(3):
                try:
                    archive.seek(0)
                    Enrollment.objects.create(
                        participant=participant,
                        type='matricula',
                        archive=archive,
                    )
                    _last_exc = None
                    break
                except Exception as exc:
                    _last_exc = exc
                    logger.warning(
                        "Intento %d/3 fallido al subir Enrollment (participant=%s): %s",
                        _attempt + 1, participant.id, exc,
                    )
                    if _attempt < 2:
                        time.sleep(2 ** _attempt)  # 1s, 2s
            if _last_exc:
                logger.error(
                    "Error al crear Enrollment para participant=%s tras 3 intentos: %s",
                    participant.id, _last_exc, exc_info=True,
                )
                raise _last_exc

        # ── 11. Registrar condiciones especiales (si vienen) ──────────
        discapacidad = serializer_data.get('discapacidad', '').strip()
        alergia = serializer_data.get('alergia', '').strip()

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

        logger.info("Inscripción completada: registration_uuid=%s participant_id=%s", registration.uuid, participant.id)

        return Response({
            'message': 'Inscripción registrada exitosamente',
            'registration_uuid': str(registration.uuid),
            'participant_id': participant.id,
        }, status=status.HTTP_201_CREATED)
    
class IndividualCupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return IndividualCupDetailSerializer
        return IndividualCupSerializer

    def create(self, request, *args, **kwargs):
        from django.db.models import Sum
        currency = request.data.get('currency')
        partner_university_id = request.data.get('partner_university')
        pre_sale_id = request.data.get('pre_sale')

        if currency is not None and partner_university_id and pre_sale_id:
            if IndividualCup.objects.filter(
                pre_sale_id=pre_sale_id,
                partner_university_id=partner_university_id,
                is_active=True,
            ).exists():
                return Response(
                    {'partner_university': 'Esta universidad ya tiene cupos asignados en esta preventa.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                currency = int(currency)
            except (ValueError, TypeError):
                return Response(
                    {'currency': 'Debe ser un número entero.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                university = PartnerUniversity.objects.select_related('quota_type').get(
                    pk=partner_university_id, is_active=True
                )
            except PartnerUniversity.DoesNotExist:
                return Response(
                    {'partner_university': 'Universidad no encontrada.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            used = Participant.objects.filter(
                cod_university=university.code,
                is_active=True,
            ).count()

            if currency < used:
                return Response(
                    {'currency': f'La cantidad no puede ser menor a los participantes ya inscritos de esta universidad ({used}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            others_reserved = IndividualCup.objects.filter(
                pre_sale_id=pre_sale_id,
                partner_university__quota_type=university.quota_type,
                is_active=True,
            ).aggregate(total=Sum('currency'))['total'] or 0

            slot_amount = AvailableSlot.objects.filter(
                pre_sale_id=pre_sale_id,
                quota_type=university.quota_type,
                is_active=True,
            ).values_list('amount', flat=True).first() or 0

            if others_reserved + currency > slot_amount:
                return Response(
                    {'currency': f'La suma de cupos reservados ({others_reserved + currency}) supera el total de cupos disponibles para esta categoría ({slot_amount}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            used_total = Registration.objects.filter(
                pre_sale_id=pre_sale_id,
                quota_type=university.quota_type,
                is_active=True,
            ).count()

            reserved_codes = list(
                IndividualCup.objects.filter(
                    pre_sale_id=pre_sale_id,
                    partner_university__quota_type=university.quota_type,
                    is_active=True,
                ).values_list('partner_university__code', flat=True)
            )
            used_reserved = Participant.objects.filter(
                cod_university__in=reserved_codes,
                is_active=True,
            ).count() if reserved_codes else 0

            free_slots = slot_amount - (others_reserved + currency)
            non_reserved_enrollees = used_total - used_reserved
            if free_slots < non_reserved_enrollees:
                return Response(
                    {'currency': f'Los cupos directos resultantes ({free_slots}) no alcanzan para los inscritos directos ({non_reserved_enrollees}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_currency = request.data.get('currency')

        if new_currency is not None:
            try:
                new_currency = int(new_currency)
            except (ValueError, TypeError):
                return Response(
                    {'currency': 'Debe ser un número entero.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            used = Participant.objects.filter(
                cod_university=instance.partner_university.code,
                is_active=True,
            ).count()

            if new_currency < used:
                return Response(
                    {'currency': f'La cantidad no puede ser menor a los participantes ya inscritos de esta universidad ({used}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            from django.db.models import Sum
            quota_type = instance.partner_university.quota_type

            others_reserved = IndividualCup.objects.filter(
                pre_sale=instance.pre_sale,
                partner_university__quota_type=quota_type,
                is_active=True,
            ).exclude(pk=instance.pk).aggregate(total=Sum('currency'))['total'] or 0

            slot_amount = AvailableSlot.objects.filter(
                pre_sale=instance.pre_sale,
                quota_type=quota_type,
                is_active=True,
            ).values_list('amount', flat=True).first() or 0

            if others_reserved + new_currency > slot_amount:
                return Response(
                    {'currency': f'La suma de cupos reservados ({others_reserved + new_currency}) supera el total de cupos disponibles para esta categoría ({slot_amount}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            used_total = Registration.objects.filter(
                pre_sale=instance.pre_sale,
                quota_type=quota_type,
                is_active=True,
            ).count()

            reserved_codes = list(
                IndividualCup.objects.filter(
                    pre_sale=instance.pre_sale,
                    partner_university__quota_type=quota_type,
                    is_active=True,
                ).values_list('partner_university__code', flat=True)
            )
            used_reserved = Participant.objects.filter(
                cod_university__in=reserved_codes,
                is_active=True,
            ).count() if reserved_codes else 0

            free_slots = slot_amount - (others_reserved + new_currency)
            non_reserved_enrollees = used_total - used_reserved
            if free_slots < non_reserved_enrollees:
                return Response(
                    {'currency': f'Los cupos directos resultantes ({free_slots}) no alcanzan para los inscritos directos ({non_reserved_enrollees}).'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        from django.db.models import Q
        queryset = IndividualCup.objects.filter(is_active=True).select_related(
            'pre_sale', 'partner_university__quota_type'
        )
        pre_sale_id = self.request.query_params.get('pre_sale_id')
        partner_university_id = self.request.query_params.get('partner_university_id')
        quota_type_id = self.request.query_params.get('quota_type_id')
        search = self.request.query_params.get('search', '').strip()
        if pre_sale_id:
            queryset = queryset.filter(pre_sale_id=pre_sale_id)
        if partner_university_id:
            queryset = queryset.filter(partner_university_id=partner_university_id)
        if quota_type_id:
            queryset = queryset.filter(partner_university__quota_type_id=quota_type_id)
        if search:
            queryset = queryset.filter(
                Q(partner_university__name__icontains=search) |
                Q(partner_university__abbreviation__icontains=search) |
                Q(partner_university__code__icontains=search)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = list(serializer.data)

        # Pares (pre_sale_id, quota_type_id) presentes en el resultado
        slot_keys = {(cup.pre_sale_id, cup.partner_university.quota_type_id) for cup in queryset}
        pre_sale_ids = {k[0] for k in slot_keys}

        # used: inscritos por universidad
        codes = [cup.partner_university.code for cup in queryset]
        participant_counts = (
            Participant.objects.filter(cod_university__in=codes, is_active=True)
            .values('cod_university')
            .annotate(count=Count('id'))
        )
        used_map = {pc['cod_university']: pc['count'] for pc in participant_counts}

        # total_amount: cupos totales del slot correspondiente
        slots = (
            AvailableSlot.objects.filter(
                pre_sale_id__in=pre_sale_ids,
                is_active=True,
            ).values('pre_sale_id', 'quota_type_id', 'amount')
        )
        amount_map = {(s['pre_sale_id'], s['quota_type_id']): s['amount'] for s in slots}

        # used_total: inscritos totales por (pre_sale, quota_type)
        reg_counts = (
            Registration.objects.filter(pre_sale_id__in=pre_sale_ids, is_active=True)
            .values('pre_sale_id', 'quota_type_id')
            .annotate(count=Count('id'))
        )
        used_total_map = {(r['pre_sale_id'], r['quota_type_id']): r['count'] for r in reg_counts}

        for item, cup in zip(data, queryset):
            slot_key = (cup.pre_sale_id, cup.partner_university.quota_type_id)
            item['used'] = used_map.get(cup.partner_university.code, 0)
            item['total_amount'] = amount_map.get(slot_key, 0)
            item['used_total'] = used_total_map.get(slot_key, 0)

        quota_types = list(
            QuotaType.objects.filter(is_active=True)
            .exclude(name='General')
            .values('id', 'name')
        )

        # universities: selector para formulario de creación/edición
        pre_sale_id = request.query_params.get('pre_sale_id')
        quota_type_id = request.query_params.get('quota_type_id')

        general_id = QuotaType.objects.filter(name='General', is_active=True).values_list('id', flat=True).first()
        universities_qs = PartnerUniversity.objects.filter(is_active=True).exclude(quota_type_id=general_id)

        if quota_type_id:
            universities_qs = universities_qs.filter(quota_type_id=quota_type_id)

        if pre_sale_id:
            already_assigned = IndividualCup.objects.filter(
                pre_sale_id=pre_sale_id,
                is_active=True,
            ).values_list('partner_university_id', flat=True)
            universities_qs = universities_qs.exclude(id__in=already_assigned)

        universities = [
            {
                'id': u['id'],
                'name': u['name'],
                'abbreviation': u['abbreviation'],
                'quota_type': u['quota_type_id'],
            }
            for u in universities_qs.values('id', 'name', 'abbreviation', 'quota_type_id')
        ]

        return Response({
            'pre_sales': get_pre_sales_with_default(),
            'quota_types': quota_types,
            'universities': universities,
            'results': data,
        })


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
    

def get_slots_data(pre_sale_id: int):
    with connection.cursor() as cursor:
        cursor.execute('SELECT get_slots_data(%s)', [pre_sale_id])
        row = cursor.fetchone()
    return row[0]


class AvailableSlotsSSEView(View):

    def get(self, request):
        def event_stream():
            while True:
                try:
                    now = timezone.now()
                    pre_sale = PreSale.objects.filter(
                        start_date__lte=now,
                        end_date__gte=now,
                        is_active=True,
                    ).values_list('id', flat=True).first()
                    if pre_sale is None:
                        yield f"data: {json.dumps([])}\n\n"
                        time.sleep(10)
                        continue
                    data = get_slots_data(pre_sale)
                    yield f"data: {json.dumps(data)}\n\n"
                    time.sleep(10)
                except GeneratorExit:
                    break
                except Exception:
                    break

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ActivePhaseView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()
        pre_sale = PreSale.objects.filter(
            start_date__lte=now,
            end_date__gte=now,
            is_active=True,
        ).first()

        if not pre_sale:
            return Response({'active': False, 'current_phase': None})

        slots = (
            AvailableSlot.objects
            .filter(pre_sale=pre_sale, is_active=True)
            .select_related('quota_type')
            .order_by('quota_type__category_order', 'quota_type__tier_order')
        )

        categories: dict[str, list] = {}
        category_order: list[str] = []
        for slot in slots:
            qt = slot.quota_type
            cat = qt.category or qt.name
            if cat not in categories:
                categories[cat] = []
                category_order.append(cat)

            benefits = qt.benefits or ''

            if qt.currency == 'PEN':
                display_price = f'S/ {slot.mount:.2f}'
            elif qt.currency == 'USD':
                display_price = f'${slot.mount:.2f}'
            else:
                display_price = f'{slot.mount:.2f}'

            categories[cat].append({
                'origin': qt.name,
                'benefits': benefits,
                'display_price': display_price,
                'currency': qt.currency,
            })

        tickets = [{'category': cat, 'tiers': categories[cat]} for cat in category_order]

        return Response({
            'active': True,
            'current_phase': {
                'id': f'{pre_sale.pk:02d}',
                'name': pre_sale.name,
                'start_date': pre_sale.start_date.date().isoformat(),
                'end_date': pre_sale.end_date.date().isoformat(),
                'tickets': tickets,
            },
        })


def _format_price(mount, currency):
    amount = int(mount) if mount == int(mount) else mount
    if currency == 'PEN':
        return f'S/ {amount}'
    if currency == 'USD':
        return f'$ {amount}'
    return str(amount)


class PhasesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()
        pre_sales = PreSale.objects.filter(is_active=True).order_by('start_date')

        slots_qs = (
            AvailableSlot.objects
            .filter(is_active=True)
            .select_related('quota_type')
            .values('pre_sale_id', 'quota_type__name', 'quota_type__currency', 'mount', 'amount')
        )
        slots_by_presale = {}
        for s in slots_qs:
            slots_by_presale.setdefault(s['pre_sale_id'], []).append(s)

        data = []
        for idx, ps in enumerate(pre_sales):
            if ps.start_date > now:
                phase_status = 'upcoming'
            elif ps.end_date < now:
                phase_status = 'past'
            else:
                phase_status = 'active'

            tiers = [
                {
                    'label': s['quota_type__name'],
                    'spots': s['amount'],
                    'price': _format_price(s['mount'], s['quota_type__currency']),
                    'currency': s['quota_type__currency'],
                }
                for s in slots_by_presale.get(ps.pk, [])
            ]

            data.append({
                'id': f'{ps.pk:02d}',
                'name': ps.name,
                'start_date': ps.start_date.date().isoformat(),
                'end_date': ps.end_date.date().isoformat(),
                'status': phase_status,
                'tiers': tiers,
            })

        return Response(data)


class IndividualCupsSSEView(View):

    def get(self, request):
        cod_university = request.GET.get('cod_university', '').strip()
        if not cod_university:
            from django.http import HttpResponse
            return HttpResponse('cod_university requerido', status=400)

        def event_stream():
            while True:
                try:
                    now = timezone.now()
                    pre_sale = PreSale.objects.filter(
                        start_date__lte=now,
                        end_date__gte=now,
                        is_active=True,
                    ).order_by('-start_date').first()

                    if not pre_sale or not pre_sale.booking_mode:
                        yield f"data: {json.dumps({'available_cups': None})}\n\n"
                        time.sleep(10)
                        continue

                    try:
                        university = PartnerUniversity.objects.get(
                            code=cod_university, is_active=True
                        )
                        individual_cup = IndividualCup.objects.get(
                            pre_sale=pre_sale,
                            partner_university=university,
                            is_active=True,
                        )
                        used = Participant.objects.filter(
                            cod_university=cod_university,
                            is_active=True,
                        ).count()
                        available = individual_cup.currency - used
                    except (PartnerUniversity.DoesNotExist, IndividualCup.DoesNotExist):
                        available = 0

                    yield f"data: {json.dumps({'available_cups': available})}\n\n"
                    time.sleep(10)
                except GeneratorExit:
                    break
                except Exception:
                    break

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
