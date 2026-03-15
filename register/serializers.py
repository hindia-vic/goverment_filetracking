from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, Department, File, FileMovement, 
    FileRequest, Notification, ActivityLog, FileVersion, FileTag
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for Django User model"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'is_active', 'created_at', 'user_count']
        read_only_fields = ['id', 'created_at']
    
    def get_user_count(self, obj):
        return obj.users.count()


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer(read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'role', 'role_display', 'department', 'department_name',
            'employee_id', 'phone', 'is_active', 'created_at', 'updated_at',
            'is_admin', 'is_registry', 'is_department_user'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FileTagSerializer(serializers.ModelSerializer):
    """Serializer for FileTag model"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = FileTag
        fields = ['id', 'name', 'color', 'description', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['id', 'created_at']


class FileVersionSerializer(serializers.ModelSerializer):
    """Serializer for FileVersion model"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = FileVersion
        fields = [
            'id', 'version_number', 'file', 'changes_summary', 
            'uploaded_by', 'uploaded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FileListSerializer(serializers.ModelSerializer):
    """Serializer for File list view"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    current_holder_name = serializers.CharField(source='current_holder.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    tags = FileTagSerializer(many=True, read_only=True)
    
    class Meta:
        model = File
        fields = [
            'id', 'reference', 'title', 'department', 'department_name',
            'status', 'status_display', 'priority', 'priority_display',
            'current_holder', 'current_holder_name', 'created_at', 
            'checked_out_at', 'due_date', 'is_overdue', 'tags'
        ]


class FileDetailSerializer(serializers.ModelSerializer):
    """Serializer for File detail view"""
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department', write_only=True
    )
    current_holder = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    versions = FileVersionSerializer(many=True, read_only=True)
    tags = FileTagSerializer(many=True, read_only=True)
    
    class Meta:
        model = File
        fields = [
            'id', 'uuid', 'reference', 'title', 'description', 
            'department', 'department_id', 'priority', 'priority_display',
            'status', 'status_display', 'current_holder', 'created_by',
            'created_at', 'updated_at', 'checked_out_at', 'due_date',
            'qr_code', 'archived_at', 'archive_reason', 'versions',
            'is_overdue', 'tags'
        ]
        read_only_fields = ['id', 'uuid', 'reference', 'created_at', 'updated_at']


class FileMovementSerializer(serializers.ModelSerializer):
    """Serializer for FileMovement model"""
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.get_full_name', read_only=True)
    
    class Meta:
        model = FileMovement
        fields = [
            'id', 'file', 'from_user', 'from_user_name', 
            'to_user', 'to_user_name', 'movement_type',
            'notes', 'processed_by', 'processed_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FileRequestSerializer(serializers.ModelSerializer):
    """Serializer for FileRequest model"""
    file = FileListSerializer(read_only=True)
    file_id = serializers.PrimaryKeyRelatedField(
        queryset=File.objects.all(), source='file', write_only=True
    )
    requesting_user = UserSerializer(read_only=True)
    requesting_department = DepartmentSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    processed_by_user = UserSerializer(source='processed_by', read_only=True)
    
    class Meta:
        model = FileRequest
        fields = [
            'id', 'file', 'file_id', 'requesting_user', 'requesting_department',
            'purpose', 'status', 'status_display', 'pickup_date',
            'registry_notes', 'processed_by', 'processed_by_user', 'processed_at',
            'user_confirmed', 'confirmed_at', 'user_confirmation_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    file_reference = serializers.CharField(source='file.reference', read_only=True)
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'file', 'file_reference', 'recipient', 'recipient_name',
            'sender', 'sender_name', 'notification_type', 'notification_type_display',
            'title', 'message', 'status', 'is_approved', 'approval_notes',
            'pickup_date', 'created_at', 'read_at'
        ]
        read_only_fields = ['id', 'created_at']


class ActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for ActivityLog model"""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = ActivityLog
        fields = [
            'id', 'user', 'user_name', 'action', 'action_display',
            'description', 'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# Write-only serializers for API operations
class FileCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating File"""
    class Meta:
        model = File
        fields = ['title', 'description', 'department', 'priority']
    
    def create(self, validated_data):
        department = validated_data['department']
        year = department.files.count() + 1
        validated_data['year'] = timezone.now().year
        validated_data['sequence'] = year
        
        # Generate reference number
        ref_number = f"{department.code}/{validated_data['year']}/{year:04d}"
        validated_data['reference'] = ref_number
        
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class FileRequestCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating FileRequest"""
    class Meta:
        model = FileRequest
        fields = ['file', 'requesting_department', 'purpose']
    
    def create(self, validated_data):
        validated_data['requesting_user'] = self.context['request'].user
        return super().create(validated_data)


class FileRequestActionSerializer(serializers.Serializer):
    """Serializer for approving/rejecting FileRequest"""
    pickup_date = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


# Import timezone for the serializer
from django.utils import timezone
