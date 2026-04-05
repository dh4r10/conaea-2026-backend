from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import SpecialCondition, Participant, ParticipantSpecialCondition, Enrollment, PartnerUniversity, Delegate
from register.models import AvailableSlot
from .serializers import (
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
    
class ParticipantByDNIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        dni = request.query_params.get('dni', '').strip()

        if not dni:
            return Response(
                {'error': 'El DNI es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            participant = Participant.objects.select_related(
                'registration__quota_type',
                'registration__pre_sale',
            ).get(identity_document=dni, is_active=True)
        except Participant.DoesNotExist:
            return Response(
                {'error': 'No se encontró ningún participante con ese DNI'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Obtener monto desde available_slot
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