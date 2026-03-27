from rest_framework import serializers
from .models import Network, Partner, PartnerNetwork


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = '__all__'


class PartnerNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerNetwork
        fields = '__all__'


class PartnerNetworkDetailSerializer(serializers.ModelSerializer):
    network = NetworkSerializer(read_only=True)

    class Meta:
        model = PartnerNetwork
        fields = '__all__'


class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = '__all__'


class PartnerDetailSerializer(serializers.ModelSerializer):
    networks = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = '__all__'

    def get_networks(self, obj):
        networks = PartnerNetwork.objects.filter(
            partner=obj,
            is_active=True
        )
        return PartnerNetworkDetailSerializer(networks, many=True).data