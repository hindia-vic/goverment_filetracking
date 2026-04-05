"""
Error handling and monitoring middleware
"""
import logging
import traceback
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """
    Middleware to catch and log unhandled errors
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_exception(self, request, exception):
        """Log errors and return appropriate response"""
        # Log the error with full traceback
        error_msg = f"Error processing {request.path}: {str(exception)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Don't expose internal errors in production
        from django.conf import settings
        if not settings.DEBUG:
            # Rate limit error notifications to avoid spam
            error_key = f"error_notif_{request.user.id}"
            if not cache.get(error_key):
                # Could integrate with error reporting service here
                cache.set(error_key, True, 300)  # 5 minute cooldown
            
            return JsonResponse({
                'error': 'An unexpected error occurred. Please contact support if this persists.',
                'error_code': 'INTERNAL_ERROR'
            }, status=500)
        
        return None  # Let Django's debug page handle it in debug mode


class RequestLoggingMiddleware:
    """
    Log all requests for monitoring and debugging
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip logging for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health/':
            return self.get_response(request)
        
        # Log request
        logger.debug(f"{request.method} {request.path}")
        
        response = self.get_response(request)
        
        # Log slow requests (> 2 seconds)
        import time
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            if duration > 2:
                logger.warning(
                    f"Slow request: {request.method} {request.path} took {duration:.2f}s"
                )
        
        return response
    
    def process_request(self, request):
        import time
        request._start_time = time.time()
        return None