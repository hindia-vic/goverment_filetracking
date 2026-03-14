# register/context_processors.py
from .models import Notification, FileRequest, UserProfile

def notification_count(request):
    """Add unread notification count to all templates"""
    if request.user.is_authenticated:
        unread = Notification.objects.filter(
            recipient=request.user,
            status='pending'
        ).count()
        
        # Get recent notifications
        recent_notifications = Notification.objects.filter(
            recipient=request.user
        )[:5]
        
        # Get pending requests count for registry/admin
        pending_requests_count = 0
        if hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin']:
            pending_requests_count = FileRequest.objects.filter(status='pending').count()
        
        return {
            'unread_notifications': unread,
            'recent_notifications': recent_notifications,
            'pending_requests_count': pending_requests_count,
        }
    return {
        'unread_notifications': 0,
        'recent_notifications': [],
        'pending_requests_count': 0,
    }
