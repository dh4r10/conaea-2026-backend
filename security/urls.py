from .views import PersonalDataViewSet, UserViewSet, RegisterUserView, ValidationViewSet, ChangePasswordView
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.urls import path, include

router = routers.DefaultRouter()

router.register('personal-data', PersonalDataViewSet, basename='personal_data')
router.register('user', UserViewSet, basename='user')
router.register('validation', ValidationViewSet, basename='validation')

urlpatterns = [
    path('security/', include(router.urls)),
    path('security/register/', RegisterUserView.as_view(), name='register_user'),
    path('security/change-password/', ChangePasswordView.as_view(), name='change-password'),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]