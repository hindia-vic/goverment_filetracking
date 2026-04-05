"""
API Router configuration - imported by urls.py
"""
from rest_framework.routers import DefaultRouter

# Create router instance - imported from urls.py
router = DefaultRouter()

# Register viewsets
router.register(r'departments', __import__('register.api', fromlist=['DepartmentViewSet']).DepartmentViewSet)
router.register(r'files', __import__('register.api', fromlist=['FileViewSet']).FileViewSet)
router.register(r'movements', __import__('register.api', fromlist=['FileMovementViewSet']).FileMovementViewSet)
router.register(r'requests', __import__('register.api', fromlist=['FileRequestViewSet']).FileRequestViewSet)
router.register(r'notifications', __import__('register.api', fromlist=['NotificationViewSet']).NotificationViewSet)
router.register(r'activity', __import__('register.api', fromlist=['ActivityLogViewSet']).ActivityLogViewSet)
router.register(r'profiles', __import__('register.api', fromlist=['UserProfileViewSet']).UserProfileViewSet)