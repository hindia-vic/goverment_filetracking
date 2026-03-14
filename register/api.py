from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    UserProfile, Department, File, FileMovement, 
    FileRequest, Notification, ActivityLog
)
from .serializers import (
    UserSerializer, UserProfileSerializer, DepartmentSerializer,
    FileListSerializer, FileDetailSerializer, FileMovementSerializer,
    FileRequestSerializer, NotificationSerializer, ActivityLogSerializer,
    FileCreateSerializer, FileRequestCreateSerializer, FileRequestActionSerializer
)
from .signals import log_activity


class IsAdminUser(permissions.BasePermission):
    """Custom permission to only allow admins to access"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['admin', 'registry']
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read access to all, write access to admins only"""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['admin', 'registry']
        )


class DepartmentViewSet(viewsets.ModelViewSet):
    """API endpoint for Departments"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    
    def get_queryset(self):
        # Filter by active status
        queryset = Department.objects.all()
        active_only = self.request.query_params.get('active', None)
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        return queryset


class FileViewSet(viewsets.ModelViewSet):
    """API endpoint for Files"""
    queryset = File.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FileListSerializer
        return FileDetailSerializer
    
    def get_queryset(self):
        queryset = File.objects.select_related(
            'department', 'current_holder', 'created_by'
        ).prefetch_related('versions')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by department
        department = self.request.query_params.get('department', None)
        if department:
            queryset = queryset.filter(department_id=department)
        
        # Filter by priority
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Search by title or reference
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(reference__icontains=search)
            )
        
        # Filter archived
        include_archived = self.request.query_params.get('include_archived', None)
        if not include_archived or include_archived.lower() != 'true':
            queryset = queryset.exclude(status='archived')
        
        return queryset
    
    def perform_create(self, serializer):
        file = serializer.save()
        log_activity(
            user=self.request.user,
            action='file_created',
            description=f"Created file {file.reference}"
        )
    
    @action(detail=True, methods=['post'])
    def checkout(self, request, pk=None):
        """Checkout a file to a user"""
        file = self.get_object()
        user_id = request.data.get('user_id')
        due_date = request.data.get('due_date')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create file movement
        movement = FileMovement.objects.create(
            file=file,
            from_user=request.user,
            to_user=user,
            movement_type='checkout',
            notes=request.data.get('notes', ''),
            processed_by=request.user
        )
        
        # Update file
        file.status = 'checked_out'
        file.current_holder = user
        file.checked_out_at = timezone.now()
        if due_date:
            file.due_date = due_date
        else:
            file.due_date = timezone.now() + timedelta(days=7)
        file.save()
        
        log_activity(
            user=request.user,
            action='file_checkout',
            description=f"Checked out file {file.reference} to {user.get_full_name()}"
        )
        
        return Response(FileMovementSerializer(movement).data)
    
    @action(detail=True, methods=['post'])
    def checkin(self, request, pk=None):
        """Checkin a file back to registry"""
        file = self.get_object()
        
        # Create file movement
        movement = FileMovement.objects.create(
            file=file,
            from_user=file.current_holder,
            to_user=request.user,
            movement_type='checkin',
            notes=request.data.get('notes', ''),
            processed_by=request.user
        )
        
        # Update file
        file.status = 'in_registry'
        file.current_holder = None
        file.checked_out_at = None
        file.due_date = None
        file.save()
        
        log_activity(
            user=request.user,
            action='file_checkin',
            description=f"Checked in file {file.reference}"
        )
        
        return Response(FileMovementSerializer(movement).data)
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a file"""
        file = self.get_object()
        
        file.status = 'archived'
        file.archived_at = timezone.now()
        file.archived_by = request.user
        file.archive_reason = request.data.get('reason', '')
        file.save()
        
        log_activity(
            user=request.user,
            action='file_archived',
            description=f"Archived file {file.reference}"
        )
        
        return Response(FileDetailSerializer(file).data)
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a file from archive"""
        file = self.get_object()
        
        file.status = 'in_registry'
        file.archived_at = None
        file.archived_by = None
        file.archive_reason = ''
        file.save()
        
        log_activity(
            user=request.user,
            action='file_restored',
            description=f"Restored file {file.reference} from archive"
        )
        
        return Response(FileDetailSerializer(file).data)


class FileMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for File Movements (read-only)"""
    queryset = FileMovement.objects.all()
    serializer_class = FileMovementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = FileMovement.objects.select_related(
            'file', 'from_user', 'to_user', 'processed_by'
        )
        
        # Filter by file
        file_id = self.request.query_params.get('file', None)
        if file_id:
            queryset = queryset.filter(file_id=file_id)
        
        # Filter by user
        user_id = self.request.query_params.get('user', None)
        if user_id:
            queryset = queryset.filter(
                Q(from_user_id=user_id) | Q(to_user_id=user_id)
            )
        
        return queryset


class FileRequestViewSet(viewsets.ModelViewSet):
    """API endpoint for File Requests"""
    queryset = FileRequest.objects.all()
    serializer_class = FileRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = FileRequest.objects.select_related(
            'file', 'requesting_user', 'requesting_department', 'processed_by'
        )
        
        # Non-admin users can only see their own requests
        if not (user.is_superuser or 
                (hasattr(user, 'profile') and user.profile.role in ['admin', 'registry'])):
            queryset = queryset.filter(requesting_user=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'create':
            return FileRequestCreateSerializer
        return FileRequestSerializer
    
    def perform_create(self, serializer):
        request = serializer.save()
        log_activity(
            user=self.request.user,
            action='request_created',
            description=f"Created file request for {request.file.reference}"
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a file request"""
        file_request = self.get_object()
        serializer = FileRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file_request.approve(
            processed_by=request.user,
            pickup_date=serializer.validated_data.get('pickup_date'),
            notes=serializer.validated_data.get('notes', '')
        )
        
        log_activity(
            user=request.user,
            action='request_approved',
            description=f"Approved request for file {file_request.file.reference}"
        )
        
        return Response(FileRequestSerializer(file_request).data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a file request"""
        file_request = self.get_object()
        serializer = FileRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        file_request.reject(
            processed_by=request.user,
            reason=serializer.validated_data.get('notes', '')
        )
        
        log_activity(
            user=request.user,
            action='request_rejected',
            description=f"Rejected request for file {file_request.file.reference}"
        )
        
        return Response(FileRequestSerializer(file_request).data)
    
    @action(detail=True, methods=['post'])
    def mark_handed_over(self, request, pk=None):
        """Mark request as handed over"""
        file_request = self.get_object()
        
        file_request.mark_handed_over(
            processed_by=request.user,
            notes=request.data.get('notes', '')
        )
        
        log_activity(
            user=request.user,
            action='request_handed_over',
            description=f"Handed over file {file_request.file.reference}"
        )
        
        return Response(FileRequestSerializer(file_request).data)
    
    @action(detail=True, methods=['post'])
    def confirm_receipt(self, request, pk=None):
        """Confirm file receipt"""
        file_request = self.get_object()
        
        file_request.confirm_receipt(
            notes=request.data.get('notes', '')
        )
        
        log_activity(
            user=request.user,
            action='request_confirmed',
            description=f"Confirmed receipt of file {file_request.file.reference}"
        )
        
        return Response(FileRequestSerializer(file_request).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for Notifications (read-only)"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        
        if notification.recipient != request.user:
            return Response(
                {'error': 'You can only mark your own notifications as read'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        notification.mark_as_read()
        return Response(NotificationSerializer(notification).data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        Notification.objects.filter(
            recipient=request.user, 
            status='pending'
        ).update(status='read', read_at=timezone.now())
        
        return Response({'message': 'All notifications marked as read'})


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for Activity Logs (admin/registry only)"""
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user')
        
        # Filter by user
        user_id = self.request.query_params.get('user', None)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action
        action = self.request.query_params.get('action', None)
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for User Profiles (read-only)"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = UserProfile.objects.select_related('user', 'department')
        
        # Non-admin users can only see their own profile
        if not (user.is_superuser or 
                (hasattr(user, 'profile') and user.profile.role in ['admin', 'registry'])):
            queryset = queryset.filter(user=user)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        try:
            profile = request.user.profile
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


# Simple API status endpoint
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_status(request):
    """API status endpoint"""
    return Response({
        'status': 'online',
        'version': '1.0.0',
        'user': request.user.username,
        'timestamp': timezone.now().isoformat()
    })


# Dashboard statistics endpoint
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """Get dashboard statistics"""
    user = request.user
    is_admin = user.is_superuser or (
        hasattr(user, 'profile') and 
        user.profile.role in ['admin', 'registry']
    )
    
    stats = {}
    
    # Files stats
    stats['total_files'] = File.objects.count()
    stats['checked_out_files'] = File.objects.filter(status='checked_out').count()
    stats['overdue_files'] = File.objects.filter(status='overdue').count()
    stats['archived_files'] = File.objects.filter(status='archived').count()
    
    # Requests stats
    stats['pending_requests'] = FileRequest.objects.filter(status='pending').count()
    stats['ready_for_pickup'] = FileRequest.objects.filter(status='ready_for_pickup').count()
    
    if is_admin:
        # Notifications
        stats['unread_notifications'] = Notification.objects.filter(
            recipient=user, 
            status='pending'
        ).count()
        
        # Recent activity
        stats['recent_activity'] = ActivityLog.objects.select_related('user')[:10].count()
    else:
        # User's requests
        stats['my_requests'] = FileRequest.objects.filter(requesting_user=user).count()
        stats['my_pending_requests'] = FileRequest.objects.filter(
            requesting_user=user, 
            status='pending'
        ).count()
        
        # User's notifications
        stats['unread_notifications'] = Notification.objects.filter(
            recipient=user, 
            status='pending'
        ).count()
        
        # Files held by user
        stats['files_held'] = File.objects.filter(current_holder=user).count()
    
    return Response(stats)
