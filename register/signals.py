from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import File, FileMovement, UserProfile, ActivityLog


def log_activity(user, action, description, request=None, metadata=None):
    """Helper function to log user activities"""
    ip_address = None
    user_agent = ''
    
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    ActivityLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {}
    )


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    log_activity(user, 'login', f'{user.username} logged in', request)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        log_activity(user, 'logout', f'{user.username} logged out', request)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile automatically when a new user is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)
        log_activity(instance, 'user_create', f'User account created: {instance.username}')


@receiver(post_save, sender=FileMovement)
def log_movement(sender, instance, created, **kwargs):
    """Additional logging if needed"""
    if created and instance.action == 'checkout':
        # Could trigger email notification here
        pass


@receiver(post_save, sender=File)
def notify_overdue(sender, instance, **kwargs):
    """Send notification when file becomes overdue"""
    if instance.status == 'overdue':
        print(f"ALERT: File {instance.reference} is now overdue!")
        # Send email notification to file holder
        if instance.current_holder:
            try:
                from register.emails import send_overdue_notification
                send_overdue_notification(instance, instance.current_holder)
            except Exception as e:
                print(f"Overdue email notification failed: {e}")