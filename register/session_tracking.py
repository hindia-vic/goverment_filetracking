from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model

import logging

logger = logging.getLogger(__name__)


class SessionTrackingMiddleware(MiddlewareMixin):
    """Track user sessions"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            self.track_activity(request)
    
    def track_activity(self, request):
        """Update user's last activity timestamp"""
        from register.models import UserSession
        from django.utils import timezone
        
        session_key = request.session.session_key
        if not session_key:
            return
        
        # Get IP address
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Update or create session record
        try:
            session, created = UserSession.objects.update_or_create(
                session_key=session_key,
                defaults={
                    'user': request.user,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'last_activity': timezone.now(),
                    'is_active': True,
                }
            )
        except Exception as e:
            logger.error(f"Failed to track session: {e}")
    
    def get_client_ip(self, request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    """Handle user login"""
    from register.models import UserSession, AccessLog
    from django.utils import timezone
    
    session_key = request.session.session_key
    if not session_key:
        return
    
    ip_address = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Create/update session
    try:
        UserSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                'user': user,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'last_activity': timezone.now(),
                'is_active': True,
            }
        )
    except Exception as e:
        logger.error(f"Failed to create session on login: {e}")
    
    # Log access
    try:
        AccessLog.objects.create(
            user=user,
            action='login',
            ip_address=ip_address,
            user_agent=user_agent,
            details='User logged in'
        )
    except Exception as e:
        logger.error(f"Failed to log access on login: {e}")


@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    """Handle user logout"""
    from register.models import UserSession, AccessLog
    
    session_key = request.session.session_key
    if not session_key:
        return
    
    ip_address = request.META.get('REMOTE_ADDR', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Deactivate session
    try:
        UserSession.objects.filter(session_key=session_key).update(is_active=False)
    except Exception as e:
        logger.error(f"Failed to deactivate session on logout: {e}")
    
    # Log access
    if user and user.is_authenticated:
        try:
            AccessLog.objects.create(
                user=user,
                action='logout',
                ip_address=ip_address,
                user_agent=user_agent,
                details='User logged out'
            )
        except Exception as e:
            logger.error(f"Failed to log access on logout: {e}")


def log_access(user, action, request=None, file=None, details=''):
    """Helper function to log access"""
    from register.models import AccessLog
    
    ip_address = ''
    user_agent = ''
    
    if request:
        ip_address = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    try:
        AccessLog.objects.create(
            user=user,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            file=file,
        )
    except Exception as e:
        logger.error(f"Failed to log access: {e}")