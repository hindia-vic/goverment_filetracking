"""
Custom middleware for audit logging all file operations
"""
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import User
from register.models import ActivityLog

logger = logging.getLogger(__name__)

# URLs that should be logged
AUDITABLE_PATHS = [
    '/register/files/',
    '/register/requests/',
    '/register/departments/',
    '/register/users/',
]

# Actions that should be logged
AUDIT_ACTIONS = {
    'POST': ['create', 'add', 'upload', 'submit', 'approve', 'reject', 'check', 'return'],
    'PUT': ['update', 'edit', 'modify'],
    'DELETE': ['delete', 'remove'],
    'GET': ['download', 'export'],
}


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware to log all important file operations for audit trail
    """
    
    def process_request(self, request):
        # Store start time for measuring request duration
        request._audit_start_time = None
        return None
    
    def process_response(self, request, response):
        # Skip logging for certain responses
        if not request.user.is_authenticated:
            return response
        
        # Only log auditable paths
        if not any(request.path.startswith(p) for p in AUDITABLE_PATHS):
            return response
        
        # Determine action type
        action = self._get_action(request, response)
        if not action:
            return response
        
        # Log the activity
        try:
            self._create_audit_log(request, action, response.status_code)
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
        
        return response
    
    def _get_action(self, request, response):
        """Determine the action type based on request method and path"""
        method = request.method
        
        # Only log POST, PUT, DELETE and certain GET actions
        if method not in ['POST', 'PUT', 'DELETE', 'GET']:
            return None
        
        path = request.path.lower()
        
        # Check for specific actions in path
        if method == 'GET':
            if 'download' in path:
                return 'file_download'
            elif 'export' in path:
                return 'export'
            return None
        
        if method == 'POST':
            if 'create' in path or 'add' in path:
                return 'create'
            elif 'upload' in path:
                return 'upload'
            elif 'approve' in path:
                return 'approve'
            elif 'reject' in path:
                return 'reject'
            elif 'check' in path and 'in' in path:
                return 'checkin'
            elif 'check' in path and 'out' in path:
                return 'checkout'
            elif 'return' in path:
                return 'return'
            elif 'submit' in path:
                return 'submit'
        
        if method == 'PUT':
            return 'update'
        
        if method == 'DELETE':
            return 'delete'
        
        return None
    
    def _create_audit_log(self, request, action, status_code):
        """Create an ActivityLog entry for the action"""
        # Skip if response was not successful (except for GET)
        if status_code >= 400 and request.method != 'GET':
            return
        
        # Get file reference if applicable
        file_ref = self._extract_file_reference(request)
        
        # Create the activity log
        ActivityLog.objects.create(
            user=request.user,
            action=action,
            description=self._get_description(request, action, file_ref),
            ip_address=self._get_client_ip(request),
        )
    
    def _extract_file_reference(self, request):
        """Extract file reference from request if applicable"""
        # Try to get UUID from URL
        import re
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        match = re.search(uuid_pattern, request.path)
        if match:
            from register.models import File
            file = File.objects.filter(uuid=match.group()).first()
            if file:
                return file.reference
        return None
    
    def _get_description(self, request, action, file_ref):
        """Generate description for the audit log"""
        descriptions = {
            'file_download': f"Downloaded file: {file_ref or 'N/A'}",
            'create': f"Created new resource via {request.path}",
            'upload': f"Uploaded document to file: {file_ref or 'N/A'}",
            'approve': f"Approved request for file: {file_ref or 'N/A'}",
            'reject': f"Rejected request for file: {file_ref or 'N/A'}",
            'checkin': f"Checked in file: {file_ref or 'N/A'}",
            'checkout': f"Checked out file: {file_ref or 'N/A'}",
            'return': f"Returned file: {file_ref or 'N/A'}",
            'update': f"Updated resource via {request.path}",
            'delete': f"Deleted resource via {request.path}",
            'export': f"Exported data from {request.path}",
        }
        return descriptions.get(action, f"Action: {action}")
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'Unknown')