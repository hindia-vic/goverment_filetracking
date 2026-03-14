from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

class EmployeeIDBackend(ModelBackend):
    """Custom authentication backend that allows login with employee ID"""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # First try to authenticate with username
        try:
            user = User.objects.get(username=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
        
        # Then try to find by employee ID
        from .models import UserProfile
        try:
            profile = UserProfile.objects.get(employee_id=username)
            user = profile.user
            if user.check_password(password):
                return user
        except UserProfile.DoesNotExist:
            pass
        
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
