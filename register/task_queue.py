"""
Task Queue System for File Tracking System

A lightweight, database-backed task queue for async processing of:
- Email notifications
- Webhook deliveries
- Scheduled tasks
"""

import hashlib
import json
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from register.models import Task

User = get_user_model()
_logger = logging.getLogger(__name__)


def generate_task_id(task_type, data):
    """Generate unique task ID"""
    data_str = json.dumps(data, sort_keys=True)
    hash_obj = hashlib.sha256(f"{task_type}:{data_str}".encode())
    return f"{task_type}_{hash_obj.hexdigest()[:16]}"


def add_task(task_type, task_name, payload, scheduled_at=None, max_attempts=3, priority=10, created_by=None):
    """Add a new task to the queue"""
    task_id = generate_task_id(task_type, payload)
    
    existing = Task.objects.filter(
        task_id=task_id, 
        status__in=['pending', 'running', 'retry']
    ).first()
    
    if existing:
        _logger.info(f"Task {task_id} already exists in queue")
        return existing
    
    task = Task.objects.create(
        task_id=task_id,
        task_type=task_type,
        task_name=task_name,
        payload=payload,
        max_attempts=max_attempts,
        scheduled_at=scheduled_at or timezone.now(),
        priority=priority,
        created_by=created_by
    )
    
    _logger.info(f"Task {task_id} added to queue")
    return task


def get_next_task():
    """Get the next pending task"""
    return Task.objects.filter(
        status__in=['pending', 'retry'],
        scheduled_at__lte=timezone.now()
    ).order_by('priority', 'scheduled_at').first()


def process_task(task):
    """Process a single task"""
    task.status = 'running'
    task.attempts += 1
    task.started_at = timezone.now()
    task.last_attempt_at = timezone.now()
    task.save(update_fields=['status', 'attempts', 'started_at', 'last_attempt_at', 'updated_at'])
    
    try:
        if task.task_type == 'email':
            _process_email_task(task)
        elif task.task_type == 'webhook':
            _process_webhook_task(task)
        elif task.task_type == 'notification':
            _process_notification_task(task)
        else:
            raise ValueError(f"Unknown task type: {task.task_type}")
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at', 'updated_at'])
        _logger.info(f"Task {task.task_id} completed successfully")
        return True
        
    except Exception as e:
        _logger.error(f"Task {task.task_id} failed: {str(e)}")
        task.last_error = str(e)
        if task.attempts < task.max_attempts:
            task.status = 'retry'
            task.scheduled_at = timezone.now() + timedelta(minutes=2 ** task.attempts)
        else:
            task.status = 'failed'
        task.save(update_fields=['status', 'last_error', 'scheduled_at', 'updated_at'])
        return False


def _process_email_task(task):
    """Process email task"""
    from register.emails import send_email_with_template
    
    recipient = task.payload.get('recipient', [])
    subject = task.payload.get('subject', '')
    content = task.payload.get('content', '')
    
    if isinstance(recipient, str):
        recipient = [recipient]
    
    send_email_with_template(subject, content, recipient)


def _process_webhook_task(task):
    """Process webhook task"""
    from register.webhook_service import WebhookService
    
    event_type = task.payload.get('event_type')
    file_id = task.payload.get('file_id')
    
    if file_id:
        from register.models import File
        file = File.objects.get(id=file_id)
        WebhookService.trigger_event(event_type, file)


def _process_notification_task(task):
    """Process in-app notification task"""
    from register.models import Notification, File
    
    file = File.objects.get(id=task.payload.get('file_id'))
    recipient = User.objects.get(id=task.payload.get('recipient_id'))
    
    Notification.objects.create(
        file=file,
        recipient=recipient,
        sender_id=task.payload.get('sender_id'),
        notification_type=task.payload.get('notification_type'),
        title=task.payload.get('title'),
        message=task.payload.get('message')
    )


def process_tasks_batch(batch_size=10):
    """Process a batch of tasks. Call from cron or management command."""
    processed = 0
    failed = 0
    
    for _ in range(batch_size):
        task = get_next_task()
        if not task:
            break
        
        if process_task(task):
            processed += 1
        else:
            failed += 1
    
    return {'processed': processed, 'failed': failed}


def queue_email(recipient, subject, content, priority=10):
    """Queue an email to be sent asynchronously"""
    return add_task(
        task_type='email',
        task_name=f"Send email to {recipient}",
        payload={
            'recipient': recipient,
            'subject': subject,
            'content': content,
        },
        priority=priority
    )


def queue_webhook(event_type, file, priority=5):
    """Queue a webhook to be triggered"""
    return add_task(
        task_type='webhook',
        task_name=f"Webhook: {event_type}",
        payload={
            'event_type': event_type,
            'file_id': file.id,
        },
        priority=priority
    )


def queue_notification(file, recipient, sender, notification_type, title, message, priority=10):
    """Queue an in-app notification"""
    return add_task(
        task_type='notification',
        task_name=f"Notification: {title}",
        payload={
            'file_id': file.id,
            'recipient_id': recipient.id,
            'sender_id': sender.id if sender else None,
            'notification_type': notification_type,
            'title': title,
            'message': message,
        },
        priority=priority
    )