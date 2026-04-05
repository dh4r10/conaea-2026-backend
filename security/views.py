from .models import PersonalData, User, Validation
from rest_framework.views import APIView
from .serializers import (
    PersonalDataSerializer, 
    UserSerializer,
    UserPermissionsSerializer,
    UserRegisterSerializer,
    ValidationSerializer,
    ValidationDetailSerializer
)
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

# Create your views here.

class PersonalDataViewSet(viewsets.ModelViewSet):
    queryset = PersonalData.objects.all()
    permission_classes = [
        permissions.IsAdminUser
    ]
    serializer_class = PersonalDataSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [
        permissions.IsAdminUser
    ]
    serializer_class = UserSerializer
    
    # ============================================
    # ENDPOINTS DE PERMISOS
    # ============================================
    
    def get_permissions(self):
        permission_map = {
            'current_user': [permissions.IsAuthenticated],
            'user_permissions': [permissions.IsAuthenticated],
            'user_groups': [permissions.IsAuthenticated],
        }

        return [perm() for perm in permission_map.get(self.action, [permissions.IsAdminUser])]
    
    @action(detail=False, methods=['get'], url_path='current')
    def current_user(self, request):
        """
        Obtener información completa del usuario autenticado con permisos
        GET /api/security/user/current/
        Requiere: Bearer Token
        """
        
        serializer = UserPermissionsSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def user_permissions(self, request):
        """
        Obtener solo los permisos del usuario autenticado
        GET /api/security/user/permissions/
        Requiere: Bearer Token
        """
        # Verificar que el usuario esté autenticado
        
        user = request.user
        
        if user.is_superuser:
            permissions_list = ['*']
        else:
            permissions_list = list(user.get_all_permissions())
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'permissions': permissions_list,
            'permissions_count': len(permissions_list) if permissions_list != ['*'] else 'all'
        })
    
    @action(detail=False, methods=['get'], url_path='groups')
    def user_groups(self, request):
        """
        Obtener grupos del usuario autenticado
        GET /api/security/user/groups/
        Requiere: Bearer Token
        """
    
        user = request.user
        groups = user.groups.all()
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'groups': [
                {
                    'id': group.id,
                    'name': group.name,
                    'permissions_count': group.permissions.count()
                }
                for group in groups
            ],
            'groups_count': groups.count()
        })
    
# PUBLIC VIEW

class RegisterUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Usuario creado correctamente",
                "user_id": user.id
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ValidationViewSet(viewsets.ModelViewSet):
    queryset = Validation.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ValidationDetailSerializer
        return ValidationSerializer

    def get_queryset(self):
        queryset = Validation.objects.filter(is_active=True)
        model = self.request.query_params.get('model')
        register_id = self.request.query_params.get('register_id')
        if model:
            queryset = queryset.filter(model=model)
        if register_id:
            queryset = queryset.filter(register_id=register_id)
        return queryset

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response(
                {'error': 'Contraseña actual y nueva son requeridas.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        if not user.check_password(current_password):
            return Response(
                {'error': 'La contraseña actual es incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if current_password == new_password:
            return Response(
                {'error': 'La nueva contraseña debe ser diferente a la actual.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {'message': 'Contraseña actualizada correctamente.'},
            status=status.HTTP_200_OK
        )