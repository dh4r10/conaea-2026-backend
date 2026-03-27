from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Network, Partner, PartnerNetwork
from .serializers import (
    NetworkSerializer,
    PartnerSerializer,
    PartnerDetailSerializer,
    PartnerNetworkSerializer,
    PartnerNetworkDetailSerializer,
)


class NetworkViewSet(viewsets.ModelViewSet):
    queryset = Network.objects.filter(is_active=True)
    serializer_class = NetworkSerializer
    permission_classes = [permissions.AllowAny]


class PartnerViewSet(viewsets.ModelViewSet):
    queryset = Partner.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PartnerDetailSerializer
        return PartnerSerializer

    def get_queryset(self):
        queryset = Partner.objects.filter(is_active=True)
        type = self.request.query_params.get('type')
        if type:
            queryset = queryset.filter(type=type)
        return queryset

    @action(detail=True, methods=['get'], url_path='networks')
    def networks(self, request, pk=None):
        """
        Obtener redes sociales de un partner
        GET /api/partner/partner/{id}/networks/
        """
        partner = self.get_object()
        networks = PartnerNetwork.objects.filter(
            partner=partner,
            is_active=True
        )
        serializer = PartnerNetworkDetailSerializer(networks, many=True)
        return Response(serializer.data)


class PartnerNetworkViewSet(viewsets.ModelViewSet):
    queryset = PartnerNetwork.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PartnerNetworkDetailSerializer
        return PartnerNetworkSerializer

    def get_queryset(self):
        queryset = PartnerNetwork.objects.filter(is_active=True)
        partner_id = self.request.query_params.get('partner_id')
        network_id = self.request.query_params.get('network_id')
        if partner_id:
            queryset = queryset.filter(partner_id=partner_id)
        if network_id:
            queryset = queryset.filter(network_id=network_id)
        return queryset