from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import SpecialCondition, Participant, ParticipantSpecialCondition, Enrollment, PartnerUniversity, Delegate
from security.models import Validation
from register.models import AvailableSlot
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
)
from .pagination import StandardPagination
from django.db.models import Q, Value
from django.db.models.functions import Concat


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

    def get_queryset(self):  # 👈
        queryset = PartnerUniversity.objects.filter(is_active=True).select_related('quota_type')
        quota_type_id = self.request.query_params.get('quota_type_id')
        search = self.request.query_params.get('search')
        if quota_type_id:
            queryset = queryset.filter(quota_type_id=quota_type_id)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    @action(detail=True, methods=['get'], url_path='delegates')
    def delegates(self, request, pk=None):
        university = self.get_object()
        delegates = university.delegates.filter(is_active=True)
        serializer = DelegateSerializer(delegates, many=True)
        return Response(serializer.data)


class DelegateViewSet(viewsets.ModelViewSet):
    queryset = Delegate.objects.filter(is_active=True).select_related('partner_university')
    serializer_class = DelegateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        partner_university_id = self.request.query_params.get('partner_university_id')

        if partner_university_id:
            queryset = queryset.filter(partner_university_id=partner_university_id)

        return queryset


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

        serializer = ParticipantTableSerializer(
            page,
            many=True,
            context={
                'universities': universities,
                'request': request,
                'validations': validations,  # 👈
            }
        )
        
        return paginator.get_paginated_response(serializer.data)
    
