from django.contrib.auth.models import Group, Permission
from django.conf import settings 
from django.db import models

class GroupPermission(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="group_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_groups")

    class Meta:
        managed = False  # No se gestionará la tabla directamente (ya existe en la base de datos)
        db_table = "auth_group_permissions"  # Nombre de la tabla intermedia en la base de datos
        verbose_name = "Group Permission"
        verbose_name_plural = "Group Permissions"
        app_label = 'auth'

class UserPermission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Usar el modelo de usuario personalizado
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        managed = False  # Esta tabla ya existe en la base de datos, no la gestionaremos con migraciones.
        db_table = 'security_user_user_permissions'  # Nombre de la tabla en la base de datos
        verbose_name = "User Permission"
        verbose_name_plural = "User Permissions"
        app_label = 'auth'

class UserGroup(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Usamos el modelo de usuario personalizado
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        managed = False  # No gestionamos esta tabla, ya existe en la base de datos
        db_table = 'security_user_groups'  # Nombre de la tabla intermedia en la base de datos
        verbose_name = "User Group"
        verbose_name_plural = "User Groups"
        app_label = 'auth'