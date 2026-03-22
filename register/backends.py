from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model

class EmployeeIDBackend(ModelBackend):
    """Custom authentication backend that allows login with employee ID"""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First try to authenticate with username
        user = None
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                # Check if user's profile is active
                if not self.is_user_active(user):
                    return None
                user.backend = 'register.backends.EmployeeIDBackend'
                return user
        except User.DoesNotExist:
            pass
        
        # Then try to find by employee ID
        from .models import UserProfile
        try:
            profile = UserProfile.objects.get(employee_id=username)
            user = profile.user
            if user.check_password(password):
                # Check if user's profile is active
                if not self.is_user_active(user):
                    return None
                user.backend = 'register.backends.EmployeeIDBackend'
                return user
        except UserProfile.DoesNotExist:
            pass
        
        return None
    
    def is_user_active(self, user):
        """Check if user is allowed to login based on their profile status"""
        try:
            if hasattr(user, 'profile') and user.profile:
                return user.profile.is_active
            else:
                # Try to get profile directly
                from .models import UserProfile
                profile = UserProfile.objects.get(user=user)
                return profile.is_active
        except UserProfile.DoesNotExist:
            # If no profile exists, allow login (backwards compatibility)
            return True
        except Exception:
            # If any error, allow login (fail-safe)
            return True
    
    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
            # Also check if user is still active
            if not self.is_user_active(user):
                return None
            user.backend = 'register.backends.EmployeeIDBackend'
            return user
        except User.DoesNotExist:
            return None
