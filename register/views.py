from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction as db_transaction
from rest_framework.views import APIView
from django.db.models import Sum
from .models import PreSale, QuotaType, AvailableSlot, Registration, Transaction, Refund
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
    RefundSerializer
)
from participant.serializers import ParticipantSerializer, ParticipantValidationSerializer


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
        if self.action == 'retrieve':
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
    
class InscriptionView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @db_transaction.atomic
    def post(self, request):
        # 1. Validar formulario primero
        serializer = ParticipantValidationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data
        voucher = request.FILES.get('voucher')
        archive = request.FILES.get('archive')

        if not voucher:
            return Response(
                {'error': 'El voucher de pago es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not archive:
            return Response(
                {'error': 'La ficha de matrícula es requerida'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Validar cupos disponibles
        pre_sale_id = data.get('pre_sale_id')
        quota_type_id = data.get('quota_type_id')

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

        # 3. Validar que identity_document y email no estén ya registrados
        if Participant.objects.filter(identity_document=data.get('identity_document')).exists():
            return Response(
                {'identity_document': 'Este documento ya está registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Participant.objects.filter(email=data.get('email')).exists():
            return Response(
                {'email': 'Este email ya está registrado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Crear Registration
        registration = Registration.objects.create(
            pre_sale_id=pre_sale_id,
            quota_type_id=quota_type_id,
        )

        # 5. Crear Participant
        participant_data = {
            'registration': registration.id,
            'first_name': data.get('first_name'),
            'paternal_surname': data.get('paternal_surname'),
            'maternal_surname': data.get('maternal_surname'),
            'birthdate': data.get('birthdate'),
            'identity_document': data.get('identity_document'),
            'document_type': data.get('document_type'),
            'email': data.get('email'),
            'cod_country': data.get('cod_country'),
            'cod_university': data.get('cod_university'),
            'academic_cycle': data.get('academic_cycle'),
        }

        participant_serializer = ParticipantSerializer(data=participant_data)
        if not participant_serializer.is_valid():
            raise Exception(participant_serializer.errors)
        participant = participant_serializer.save()

        # 6. Crear Enrollment con PDF
        enrollment = Enrollment.objects.create(
            participant=participant,
            type='ficha',
            archive=archive,
        )

        # 7. Crear Transaction con voucher
        transaction = Transaction.objects.create(
            registration=registration,
            payment_method=data.get('payment_method'),
            mount=slot.mount,
            voucher=voucher,
        )

        return Response({
            'registration_id': registration.id,
            'registration_uuid': str(registration.uuid),
            'participant_id': participant.id,
            'enrollment_id': enrollment.id,
            'transaction_id': transaction.id,
            'message': 'Inscripción creada exitosamente'
        }, status=status.HTTP_201_CREATED)