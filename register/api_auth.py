"""
API Key Authentication for REST Framework
"""
import hashlib
from rest_framework import authentication, exceptions
from django.utils import timezone
from register.models import APIToken


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate requests using API tokens"""
    
    keyword = 'Bearer'
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        if not auth_header.startswith(f'{self.keyword} '):
            return None
        
        token = auth_header[len(self.keyword):].strip()
        
        if not token:
            return None
        
        return self.authenticate_token(token)
    
    def authenticate_token(self, token):
        """Authenticate using the token key"""
        # Use prefix matching for security (store only first 8 chars as prefix)
        prefix = token[:8]
        
        try:
            api_token = APIToken.objects.select_related('user').get(
                key__startswith=prefix,
                is_active=True
            )
        except APIToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API token')
        
        # Check expiration
        if api_token.expires_at and api_token.expires_at < timezone.now():
            raise exceptions.AuthenticationFailed('API token has expired')
        
        # Update last used
        api_token.last_used = timezone.now()
        api_token.save(update_fields=['last_used'])
        
        return (api_token.user, api_token)


class TokenRateThrottle:
    """Custom throttle based on API token's rate limit"""
    
    def get_rate(self):
        return getattr(self, 'rate', '1000/hour')
    
    def allow_request(self, request, view):
        # Check if using API token authentication
        if hasattr(request, 'auth') and isinstance(request.auth, APIToken):
            self.rate = f"{request.auth.rate_limit}/hour"
        
        return super().allow_request(request, view)


def generate_api_token(user, name, description='', expires_days=None):
    """Helper function to generate an API token"""
    from datetime import timedelta
    
    token = APIToken.objects.create(
        user=user,
        name=name,
        description=description,
        expires_at=timezone.now() + timedelta(days=expires_days) if expires_days else None
    )
    return token