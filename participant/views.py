from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import SpecialCondition, Participant, ParticipantSpecialCondition, Enrollment, PartnerUniversity, Delegate
from security.models import Validation
from register.models import AvailableSlot, QuotaType, PreSale
from .serializers import (
    ParticipantTableSerializer,
    SpecialConditionSerializer,
    ParticipantSerializer,
    ParticipantDetailSerializer,
    ParticipantSpecialConditionSerializer,
    EnrollmentSerializer,
    ParticipantValidationSerializer,
    PartnerUniversitySerializer,
    PartnerUniversityDetailSerializer,
    DelegateSerializer,
    DelegateListSerializer,
)
from .pagination import StandardPagination

from django.db import connection
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.utils import timezone


class SpecialConditionViewSet(viewsets.ModelViewSet):
    queryset = SpecialCondition.objects.filter(is_active=True)
    serializer_class = SpecialConditionSerializer
    permission_classes = [permissions.IsAdminUser]


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.filter(is_active=True)
    permission_classes = [permissions.IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ParticipantDetailSerializer
        return ParticipantSerializer

    @action(detail=True, methods=['get'], url_path='detail')
    def full_detail(self, request, pk=None):
        """
        Obtener participante con condiciones especiales y enrollments
        GET /api/participants/participant/{id}/detail/
        """
        participant = self.get_object()
        serializer = ParticipantDetailSerializer(participant)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='enrollments')
    def enrollments(self, request, pk=None):
        """
        Obtener enrollments de un participante
        GET /api/participants/participant/{id}/enrollments/
        """
        participant = self.get_object()
        enrollments = Enrollment.objects.filter(
            participant=participant,
            is_active=True
        )
        serializer = EnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='special-conditions')
    def special_conditions(self, request, pk=None):
        """
        Obtener condiciones especiales de un participante
        GET /api/participants/participant/{id}/special-conditions/
        """
        participant = self.get_object()
        conditions = ParticipantSpecialCondition.objects.filter(
            participant=participant,
            is_active=True
        )
        serializer = ParticipantSpecialConditionSerializer(conditions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """
        Desactivar participante y todos sus registros asociados
        PATCH /api/participants/participant/{id}/deactivate/
        """
        participant = self.get_object()

        if not participant.is_active:
            return Response(
                {'detail': 'Participant is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with connection.cursor() as cursor:
            cursor.execute('CALL deactivate_participant(%s)', [participant.id])

        return Response(
            {'detail': 'Participante eliminado correctamente'},
            status=status.HTTP_200_OK
        )


class ParticipantSpecialConditionViewSet(viewsets.ModelViewSet):
    queryset = ParticipantSpecialCondition.objects.filter(is_active=True)
    serializer_class = ParticipantSpecialConditionSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = ParticipantSpecialCondition.objects.filter(is_active=True)
        participant_id = self.request.query_params.get('participant_id')
        if participant_id:
            queryset = queryset.filter(participant_id=participant_id)
        return queryset


class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.filter(is_active=True)
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = Enrollment.objects.filter(is_active=True)
        participant_id = self.request.query_params.get('participant_id')
        if participant_id:
            queryset = queryset.filter(participant_id=participant_id)
        return queryset


class PartnerUniversityViewSet(viewsets.ModelViewSet):
    queryset = PartnerUniversity.objects.filter(is_active=True).select_related('quota_type')
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action in ('retrieve', 'list'):
            return PartnerUniversityDetailSerializer
        return PartnerUniversitySerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_is_active = request.data.get('is_active')
        response = super().update(request, *args, **kwargs)
        if new_is_active is not None and str(new_is_active).lower() in ('false', '0') and instance.is_active:
            Delegate.objects.filter(partner_university=instance, is_active=True).update(is_active=False)
        return response

    def get_queryset(self):
        queryset = PartnerUniversity.objects.filter(is_active=True).select_related('quota_type')
        quota_type_id = self.request.query_params.get('quota_type_id')
        search = self.request.query_params.get('search')
        if quota_type_id:
            queryset = queryset.filter(quota_type_id=quota_type_id)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(abbreviation__icontains=search))
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        quota_types = list(QuotaType.objects.filter(is_active=True).values('id', 'name'))
        response.data['quota_types'] = quota_types
        return response

    @action(detail=False, methods=['get'], url_path='select')
    def select(self, request):
        search = request.query_params.get('search', '').strip()
        qs = PartnerUniversity.objects.filter(is_active=True).only('code', 'name', 'abbreviation')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(abbreviation__icontains=search))
        qs = qs.order_by('name')[:50]
        data = [
            {'code': u.code, 'name': u.name, 'abbreviation': u.abbreviation}
            for u in qs
        ]
        return Response(data)

    @action(detail=True, methods=['get'], url_path='delegates')
    def delegates(self, request, pk=None):
        university = self.get_object()
        delegates = university.delegates.filter(is_active=True)
        serializer = DelegateSerializer(delegates, many=True)
        return Response(serializer.data)


class DelegateViewSet(viewsets.ModelViewSet):
    queryset = Delegate.objects.filter(is_active=True).select_related('partner_university')
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return DelegateListSerializer
        return DelegateSerializer

    def get_queryset(self):
        queryset = Delegate.objects.filter(is_active=True).select_related('partner_university')
        partner_university_id = self.request.query_params.get('partner_university_id')
        search = self.request.query_params.get('search', '').strip()
        if partner_university_id:
            queryset = queryset.filter(partner_university_id=partner_university_id)
        if search:
            queryset = queryset.filter(
                Q(fullname__icontains=search) | Q(partner_university__name__icontains=search)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data['universities'] = list(
            PartnerUniversity.objects.filter(is_active=True)
            .values('id', 'name', 'abbreviation')
            .order_by('name')
        )
        return response


class ParticipantValidationView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ParticipantValidationSerializer(data=request.data)

        if serializer.is_valid():
            return Response(
                {'message': 'Formulario válido'},
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class ParticipantByIdentityView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        document = request.query_params.get('document', '').strip()
        document_type = request.query_params.get('document_type', 'DNI').strip().upper()

        if not document:
            return Response(
                {'error': 'El documento es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if document_type not in ('DNI', 'PASAPORTE'):
            return Response(
                {'error': 'El tipo de documento debe ser DNI o PASAPORTE'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if document_type == 'DNI':
            if not document.isdigit() or len(document) != 8:
                return Response(
                    {'error': 'El DNI debe tener exactamente 8 dígitos numéricos'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif document_type == 'PASAPORTE':
            if not document.isalnum() or len(document) > 11:
                return Response(
                    {'error': 'El pasaporte debe ser alfanumérico y tener como máximo 11 caracteres'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            participant = Participant.objects.select_related(
                'registration__quota_type',
                'registration__pre_sale',
            ).get(
                identity_document=document,
                document_type=document_type,
                is_active=True,
            )
        except Participant.DoesNotExist:
            return Response(
                {'error': 'No se encontró ningún participante con ese documento'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            slot = AvailableSlot.objects.get(
                pre_sale=participant.registration.pre_sale,
                quota_type=participant.registration.quota_type,
                is_active=True
            )
            mount = slot.mount
        except AvailableSlot.DoesNotExist:
            mount = None

        return Response({
            'participant_id': participant.id,
            'registration_id': participant.registration.id,
            'registration_uuid': str(participant.registration.uuid),
            'full_name': f"{participant.first_name} {participant.paternal_surname} {participant.maternal_surname}",
            'email': participant.email,
            'university_type': participant.university_type,
            'quota_type': participant.registration.quota_type.name,
            'currency': participant.registration.quota_type.currency,
            'mount': mount,
        }, status=status.HTTP_200_OK)


class ParticipantUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, pk):
        try:
            participant = Participant.objects.get(pk=pk, is_active=True)
        except Participant.DoesNotExist:
            return Response(
                {'error': 'Participante no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data

        # ── Verificar duplicados (excluyendo al mismo participante) ────
        identity_document = data.get('identity_document', '').strip()
        email = data.get('email', '').strip()

        if identity_document and Participant.objects.filter(
            identity_document=identity_document,
            is_active=True
        ).exclude(pk=pk).exists():
            return Response(
                {'identity_document': 'Ya existe un participante con este documento'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if email and Participant.objects.filter(
            email=email,
            is_active=True
        ).exclude(pk=pk).exists():
            return Response(
                {'email': 'Ya existe un participante con este correo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Actualizar campos ──────────────────────────────────────────
        updatable_fields = [
            'first_name', 'paternal_surname', 'maternal_surname',
            'birthday', 'identity_document', 'document_type',
            'cellphone', 'email',
        ]

        if participant.university_type == 'Referido':
            updatable_fields += ['academic_cycle', 'cod_university']

        for field in updatable_fields:
            value = data.get(field, '').strip() if isinstance(data.get(field), str) else data.get(field)
            if value is not None and value != '':
                setattr(participant, field, value)

        if participant.university_type == 'Referido':
            cod_country = data.get('cod_country')
            if cod_country is not None and cod_country != '':
                try:
                    participant.cod_country = int(cod_country)
                except (ValueError, TypeError):
                    return Response(
                        {'cod_country': 'Debe ser un número entero'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # ── Foto ───────────────────────────────────────────────────────
        photograph = request.FILES.get('photograph')
        if photograph:
            participant.photograph = photograph

        participant.save()

        # ── Eliminar validación de registration al editar ──────────────
        if participant.registration_id:
            Validation.objects.filter(
                model='registration',
                register_id=participant.registration_id,
            ).delete()

        # ── Condiciones especiales ─────────────────────────────────────
        SPECIAL_CONDITION_IDS = {'discapacidad': 1, 'alergia': 2}

        for field, condition_id in SPECIAL_CONDITION_IDS.items():
            value = data.get(field, '').strip() if field in data else ''
            condition = ParticipantSpecialCondition.objects.filter(
                participant=participant,
                special_condition_id=condition_id,
            ).first()
            if value:
                if condition:
                    condition.description = value
                    condition.is_active = True
                    condition.save()
                else:
                    ParticipantSpecialCondition.objects.create(
                        participant=participant,
                        special_condition_id=condition_id,
                        description=value,
                    )
            else:
                if condition and condition.is_active:
                    condition.is_active = False
                    condition.save()

        return Response({
            'message': 'Participante actualizado correctamente',
            'participant_id': participant.id,
        }, status=status.HTTP_200_OK)

# views.py

class ParticipantStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        total = Participant.objects.filter(is_active=True).count()
        
        validated_ids = Validation.objects.filter(
            model='registration',
        ).values_list('register_id', flat=True)

        validated = Participant.objects.filter(
            is_active=True,
            registration_id__in=validated_ids,
        ).count()

        return Response({
            'total': total,
            'validated': validated,
            'pending': total - validated,
        })

# participant/views.py

class ParticipantTableView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        qs = Participant.objects.filter(is_active=True).select_related(
            'registration__quota_type',
            'registration__pre_sale',
        ).prefetch_related(
            'enrollment_set',                    # 👈
            'registration__transaction_set',     # 👈
        )
        
        from security.models import Validation

        validations = set(
            Validation.objects.values_list('model', 'register_id')
        )

        # ── Filtros ───────────────────────────────────────────────
        pre_sale_id = request.query_params.get('pre_sale_id')
        document_type = request.query_params.get('document_type')
        quota_type_id = request.query_params.get('quota_type_id')
        university_type = request.query_params.get('university_type')
        university_code = request.query_params.get('university_code')
        search = request.query_params.get('search', '').strip()
        

        if pre_sale_id:
            qs = qs.filter(registration__pre_sale_id=pre_sale_id)
        if document_type:
            qs = qs.filter(document_type=document_type)
        if quota_type_id:
            qs = qs.filter(registration__quota_type_id=quota_type_id)
        if university_type:
            qs = qs.filter(university_type=university_type)
        if university_code:
            qs = qs.filter(cod_university=university_code)
        if search:
            qs = qs.annotate(
                    full_name=Concat(
                        'first_name', Value(' '),
                        'paternal_surname', Value(' '),
                        'maternal_surname',
                    )
                )
            
            qs = qs.filter(
                    Q(full_name__icontains=search) |
                    Q(identity_document__icontains=search) |
                    Q(email__icontains=search) |
                    Q(cod_university__icontains=search) |
                    Q(cod_university__in=PartnerUniversity.objects.filter(
                        name__icontains=search, is_active=True
                    ).values_list('code', flat=True))
                )

        # ── Paginación ────────────────────────────────────────────
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)

        # ── Precargar universidades Referido para evitar N+1 ──────
        referido_codes = {
            p.cod_university for p in page
            if p.university_type == 'Referido'
        }
        universities = {}
        if referido_codes:
            universities = {
                u.code: u
                for u in PartnerUniversity.objects.filter(
                    code__in=referido_codes,
                    is_active=True
                )
            }

        # ── Precargar último email por participante ────────────────
        from security.models import EmailLog
        participant_ids = [p.id for p in page]
        email_statuses = {}
        for log in EmailLog.objects.filter(participant_id__in=participant_ids).values('participant_id', 'status').order_by('participant_id', '-created_at'):
            if log['participant_id'] not in email_statuses:
                email_statuses[log['participant_id']] = log['status']

        serializer = ParticipantTableSerializer(
            page,
            many=True,
            context={
                'universities': universities,
                'request': request,
                'validations': validations,
                'email_statuses': email_statuses,
            }
        )

        response = paginator.get_paginated_response(serializer.data)
        pre_sales_qs = list(PreSale.objects.filter(is_active=True).values('id', 'name', 'start_date', 'end_date'))
        now = timezone.now()
        in_range = [p for p in pre_sales_qs if p['start_date'] <= now <= p['end_date']]
        if in_range:
            default_id = in_range[0]['id']
        else:
            past = [p for p in pre_sales_qs if p['start_date'] < now]
            default_id = max(past, key=lambda p: p['start_date'])['id'] if past else None
        response.data['pre_sales'] = [
            {'id': p['id'], 'name': p['name'], 'is_default': p['id'] == default_id}
            for p in pre_sales_qs
        ]
        response.data['quota_types'] = list(QuotaType.objects.filter(is_active=True).values('id', 'name'))
        return response
    
