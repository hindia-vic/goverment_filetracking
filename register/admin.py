# registry/admin.py
from django.contrib import admin
from .models import Department, File, FileMovement, AuditLog, UserProfile, Notification, FileRequest, ActivityLog, FileVersion


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'employee_id', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'employee_id']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['file', 'recipient', 'notification_type', 'status', 'created_at']
    list_filter = ['notification_type', 'status']
    search_fields = ['file__reference', 'recipient__username', 'title']
    date_hierarchy = 'created_at'


@admin.register(FileRequest)
class FileRequestAdmin(admin.ModelAdmin):
    list_display = ['file', 'requesting_user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['file__reference', 'requesting_user__username']
    date_hierarchy = 'created_at'


class FileMovementInline(admin.TabularInline):
    model = FileMovement
    extra = 0
    readonly_fields = ['created_at', 'signature_data']
    fields = ['action', 'from_user', 'to_user', 'from_department', 'to_department', 'created_at']


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['reference', 'title', 'status', 'current_holder', 'due_date', 'is_overdue_display']
    list_filter = ['status', 'department', 'priority', 'year']
    search_fields = ['reference', 'title', 'uuid']
    readonly_fields = ['reference', 'uuid', 'qr_code_preview', 'created_at']
    inlines = [FileMovementInline]
    date_hierarchy = 'created_at'
    
    def qr_code_preview(self, obj):
        if obj.qr_code:
            return f'<img src="{obj.qr_code.url}" width="150" />'
        return "No QR code generated"
    qr_code_preview.allow_tags = True
    
    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return "⚠️ OVERDUE"
        return "No"
    is_overdue_display.short_description = "Overdue"


@admin.register(FileMovement)
class FileMovementAdmin(admin.ModelAdmin):
    list_display = ['file', 'action', 'created_at', 'from_user', 'to_user']
    list_filter = ['action', 'created_at']
    search_fields = ['file__reference', 'signature_data']
    date_hierarchy = 'created_at'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['file', 'user', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['file__reference', 'user__username']
    date_hierarchy = 'timestamp'
    readonly_fields = ['file', 'user', 'action', 'details', 'timestamp', 'ip_address']


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description', 'ip_address', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'description']
    date_hierarchy = 'timestamp'
    readonly_fields = ['user', 'action', 'description', 'ip_address', 'user_agent', 'metadata', 'timestamp']
    
    def has_add_permission(self, request):
        return False  # Activity logs are read-only
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = ['file', 'version_number', 'change_type', 'created_by', 'created_at']
    list_filter = ['change_type', 'created_at']
    search_fields = ['file__reference', 'file__title']
    date_hierarchy = 'created_at'
    readonly_fields = ['file', 'version_number', 'title', 'description', 'department', 'created_by', 'change_type', 'notes', 'created_at']


# Register your models here.
