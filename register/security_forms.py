from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from .models import LoginAttempt, UserSession, AccessLog
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class SecureAuthenticationForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.request = request
        self.user_cache = None
    
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username and password:
            # Get client IP
            ip_address = self.get_client_ip()
            user_agent = self.request.META.get('HTTP_USER_AGENT', '') if self.request else ''
            
            # Check for account lockout
            if self.is_account_locked(username):
                raise ValidationError(
                    'Too many failed login attempts. Your account has been locked. Please try again later or contact administrator.',
                    code='locked'
                )
            
            # Check for IP lockout
            if self.is_ip_locked(ip_address):
                raise ValidationError(
                    'Too many failed login attempts from this IP address. Please try again later.',
                    code='ip_locked'
                )
            
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password
            )
            
            if self.user_cache is None:
                # Log failed attempt
                self.log_attempt(username, ip_address, user_agent, 'failed')
                raise ValidationError(
                    'Invalid username or password.',
                    code='invalid_login'
                )
            elif not self.user_cache.is_active:
                self.log_attempt(username, ip_address, user_agent, 'failed')
                raise ValidationError(
                    'This account has been deactivated.',
                    code='inactive'
                )
            else:
                # Log successful attempt
                self.log_attempt(username, ip_address, user_agent, 'success')
                
                # Log to access log
                try:
                    AccessLog.objects.create(
                        user=self.user_cache,
                        action='login',
                        ip_address=ip_address,
                        user_agent=user_agent,
                        details='Successful login'
                    )
                except Exception as e:
                    logger.error(f"Failed to create access log: {e}")
        
        return self.cleaned_data
    
    def get_client_ip(self):
        """Get client IP address from request"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = self.request.META.get('REMOTE_ADDR', '')
        return ip
    
    def log_attempt(self, username, ip_address, user_agent, status):
        """Log login attempt"""
        try:
            user = User.objects.filter(username=username).first()
            LoginAttempt.objects.create(
                user=user,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status
            )
        except Exception as e:
            logger.error(f"Failed to log login attempt: {e}")
    
    def is_account_locked(self, username):
        """Check if account has too many failed attempts"""
        from django.conf import settings
        lockout_threshold = getattr(settings, 'LOGIN_LOCKOUT_THRESHOLD', 5)
        lockout_duration = getattr(settings, 'LOGIN_LOCKOUT_DURATION', 30)  # minutes
        
        recent_attempts = LoginAttempt.objects.filter(
            username=username,
            status='failed',
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=lockout_duration)
        ).count()
        
        return recent_attempts >= lockout_threshold
    
    def is_ip_locked(self, ip_address):
        """Check if IP has too many failed attempts"""
        from django.conf import settings
        lockout_threshold = getattr(settings, 'IP_LOCKOUT_THRESHOLD', 10)
        lockout_duration = getattr(settings, 'LOGIN_LOCKOUT_DURATION', 30)
        
        recent_attempts = LoginAttempt.objects.filter(
            ip_address=ip_address,
            status='failed',
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=lockout_duration)
        ).count()
        
        return recent_attempts >= lockout_threshold
    
    def get_user(self):
        return self.user_cache


from django.contrib.auth import authenticate


class SessionManagementForm(forms.Form):
    """Form to terminate user sessions"""
    sessions = forms.ModelMultipleChoiceField(
        queryset=UserSession.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['sessions'].queryset = UserSession.objects.filter(
            user=user,
            is_active=True
        ).order_by('-last_activity')
    
    def save(self):
        sessions = self.cleaned_data['sessions']
        count = 0
        for session in sessions:
            session.is_active = False
            session.save()
            count += 1
        return count


class AccessLogFilterForm(forms.Form):
    """Form to filter access logs"""
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label='All Users'
    )
    action = forms.ChoiceField(
        choices=[('', 'All Actions')] + list(AccessLog.ACTION_CHOICES),
        required=False
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    ip_address = forms.CharField(max_length=50, required=False)