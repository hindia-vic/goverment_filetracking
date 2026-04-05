"""
Webhook service for sending notifications to external systems
"""
import json
import hmac
import hashlib
import time
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookService:
    """Service to trigger webhooks for various events"""
    
    @staticmethod
    def generate_signature(payload: dict, secret: str) -> str:
        """Generate HMAC signature for webhook payload"""
        if not secret:
            return ''
        payload_str = json.dumps(payload, sort_keys=True)
        return hmac.new(
            secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def send_webhook(webhook, event_type: str, data: dict) -> bool:
        """Send webhook to external URL"""
        from register.models import WebhookDelivery
        
        # Prepare payload
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': data
        }
        
        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=event_type,
            payload=payload,
            status='pending'
        )
        
        try:
            import requests
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'FileTrackingSystem/1.0'
            }
            
            # Add signature if secret is set
            if webhook.secret:
                signature = WebhookService.generate_signature(payload, webhook.secret)
                headers['X-Webhook-Signature'] = f'sha256={signature}'
            
            # Send request
            start_time = time.time()
            response = requests.post(
                webhook.url,
                json=payload,
                headers=headers,
                timeout=30
            )
            duration = time.time() - start_time
            
            # Update delivery record
            delivery.response_code = response.status_code
            delivery.response_body = response.text[:1000]  # Limit response size
            delivery.completed_at = timezone.now()
            
            if response.status_code >= 200 and response.status_code < 300:
                delivery.status = 'success'
                webhook.last_triggered = timezone.now()
                webhook.failure_count = 0
                webhook.last_status = 'success'
            else:
                delivery.status = 'failed'
                webhook.failure_count += 1
                webhook.last_status = 'failed'
            
            delivery.save()
            webhook.save()
            
            logger.info(f"Webhook {webhook.name} for {event_type}: {delivery.status}")
            return delivery.status == 'success'
            
        except requests.exceptions.Timeout:
            delivery.status = 'failed'
            delivery.response_body = 'Request timeout'
            delivery.completed_at = timezone.now()
            delivery.save()
            webhook.failure_count += 1
            webhook.last_status = 'timeout'
            webhook.save()
            logger.error(f"Webhook {webhook.name} timeout")
            return False
            
        except requests.exceptions.RequestException as e:
            delivery.status = 'failed'
            delivery.response_body = str(e)[:1000]
            delivery.completed_at = timezone.now()
            delivery.save()
            webhook.failure_count += 1
            webhook.last_status = 'error'
            webhook.save()
            logger.error(f"Webhook {webhook.name} error: {e}")
            return False
    
    @staticmethod
    def trigger_event(event_type: str, data: dict):
        """Trigger webhooks for all active webhooks listening to this event"""
        from register.models import Webhook
        
        # Get all active webhooks for this event type
        webhooks = Webhook.objects.filter(
            is_active=True,
            event_types__contains=[event_type]
        )
        
        for webhook in webhooks:
            try:
                WebhookService.send_webhook(webhook, event_type, data)
            except Exception as e:
                logger.error(f"Error triggering webhook {webhook.name}: {e}")
    
    @staticmethod
    def trigger_file_checkout(file, user, request_obj=None):
        """Trigger webhook for file checkout"""
        WebhookService.trigger_event('file_checkout', {
            'file_uuid': str(file.uuid),
            'file_reference': file.reference,
            'file_title': file.title,
            'checked_out_by': user.get_full_name() or user.username,
            'due_date': file.due_date.isoformat() if file.due_date else None,
            'timestamp': timezone.now().isoformat()
        })
    
    @staticmethod
    def trigger_file_checkin(file, user):
        """Trigger webhook for file checkin"""
        WebhookService.trigger_event('file_checkin', {
            'file_uuid': str(file.uuid),
            'file_reference': file.reference,
            'file_title': file.title,
            'checked_in_by': user.get_full_name() or user.username,
            'timestamp': timezone.now().isoformat()
        })
    
    @staticmethod
    def trigger_file_upload(file, user):
        """Trigger webhook for new file upload"""
        WebhookService.trigger_event('file_upload', {
            'file_uuid': str(file.uuid),
            'file_reference': file.reference,
            'file_title': file.title,
            'department': file.department.name if file.department else None,
            'uploaded_by': user.get_full_name() or user.username,
            'timestamp': timezone.now().isoformat()
        })
    
    @staticmethod
    def trigger_request_approved(request_obj):
        """Trigger webhook for request approval"""
        WebhookService.trigger_event('request_approved', {
            'request_id': request_obj.id,
            'file_reference': request_obj.file.reference,
            'file_title': request_obj.file.title,
            'requested_by': request_obj.requesting_user.get_full_name() or request_obj.requesting_user.username,
            'approved_by': request_obj.processed_by.get_full_name() if request_obj.processed_by else None,
            'timestamp': timezone.now().isoformat()
        })
    
    @staticmethod
    def trigger_request_rejected(request_obj):
        """Trigger webhook for request rejection"""
        WebhookService.trigger_event('request_rejected', {
            'request_id': request_obj.id,
            'file_reference': request_obj.file.reference,
            'file_title': request_obj.file.title,
            'requested_by': request_obj.requesting_user.get_full_name() or request_obj.requesting_user.username,
            'rejection_reason': request_obj.approval_notes,
            'timestamp': timezone.now().isoformat()
        })
    
    @staticmethod
    def trigger_file_returned(request_obj):
        """Trigger webhook for file return verification"""
        WebhookService.trigger_event('file_returned', {
            'request_id': request_obj.id,
            'file_reference': request_obj.file.reference,
            'file_title': request_obj.file.title,
            'returned_by': request_obj.requesting_user.get_full_name() or request_obj.requesting_user.username,
            'verified_by': request_obj.return_verified_by.get_full_name() if request_obj.return_verified_by else None,
            'condition': request_obj.return_condition,
            'timestamp': timezone.now().isoformat()
        })