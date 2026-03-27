from django.contrib import admin
from .models import User, PersonalData
from congress.proxy import GroupPermission, UserPermission, UserGroup
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.contrib.admin.models import LogEntry
from django.utils.translation import gettext_lazy as _
import json

# Register your models here.

admin.site.site_header = "CONANEA-2026 - Panel de Administración"
admin.site.site_title = "Panel"
admin.site.index_title = "Bienvenido al panel de administración"
admin.site.site_url = "/hola"

admin.site.register(User)
admin.site.register(PersonalData)
admin.site.register(Permission)
admin.site.register(ContentType)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'user', 'expire_date')

    def user(self, obj):
        data = obj.get_decoded()
        user_id = data.get('_auth_user_id')
        return f"User ID: {user_id}" if user_id else "Anonymous"

    def get_readable_data(self, obj):
        data = obj.get_decoded()
        return json.dumps(data, indent=4)

    def session_data(self, obj):
        return self.get_readable_data(obj)

    session_data.short_description = "Session Data"

@admin.register(GroupPermission)
class GroupPermissionAdmin(admin.ModelAdmin):
    list_display = ('group', 'permission')
    search_fields = ('group__name', 'permission__codename')
    list_filter = ('group', 'permission__content_type')

@admin.register(UserPermission)
class UserPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'permission')
    list_filter = ('user', 'permission')
    search_fields = ('user__username', 'permission__name')

@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ('user', 'group')
    list_filter = ('user', 'group')
    search_fields = ('user__username', 'group__name')

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_type', 'object_id', 'object_repr', 'action_time', 'action_flag')
    list_filter = ('action_flag', 'user')
    search_fields = ('object_repr', 'content_type__app_label', 'content_type__model', 'user__username')
    date_hierarchy = 'action_time'
    ordering = ('-action_time',)

    def get_readable_action_flag(self, obj):
        action_flags = {
            LogEntry.ADDITION: _('Addition'),
            LogEntry.CHANGE: _('Change'),
            LogEntry.DELETION: _('Deletion'),
        }
        return action_flags.get(obj.action_flag, _('Unknown'))

    get_readable_action_flag.short_description = _('Action')

    # Habilitar la visualización de las acciones en una forma legible
    list_display_links = ('user', 'content_type', 'object_id')

    def object_repr(self, obj):
        """Representación legible de la acción realizada en el objeto"""
        return f"{obj.content_type} - {obj.object_repr}"