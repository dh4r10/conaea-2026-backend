from .views import PersonalDataViewSet, UserViewSet, RegisterUserView, ValidationViewSet, ValidationAdminViewSet, ChangePasswordView, EmailLogListView, DashboardView, ResendEmailView, EmailStatusSSEView
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
router.register('validation-admin', ValidationAdminViewSet, basename='validation_admin')

urlpatterns = [
    path('security/', include(router.urls)),
    path('security/register/', RegisterUserView.as_view(), name='register_user'),
    path('security/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('security/email-logs/', EmailLogListView.as_view(), name='email_logs'),
    path('security/resend-email/', ResendEmailView.as_view(), name='resend_email'),
    path('security/email-status/sse/', EmailStatusSSEView.as_view(), name='email_status_sse'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]