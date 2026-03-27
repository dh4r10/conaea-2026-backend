from django.urls import path, include
from rest_framework import routers
from .views import (
    NetworkViewSet,
    PartnerViewSet,
    PartnerNetworkViewSet,
)

router = routers.DefaultRouter()

router.register('network', NetworkViewSet, basename='network')
router.register('partner', PartnerViewSet, basename='partner')
router.register('partner-network', PartnerNetworkViewSet, basename='partner_network')

urlpatterns = [
    path('partner/', include(router.urls)),
]