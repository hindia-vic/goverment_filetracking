"""
Management command to manage audit log retention
Auto-archive or delete old activity logs based on retention policy
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from register.models import ActivityLog, Notification


class Command(BaseCommand):
    help = 'Manage audit log retention - archive or delete old logs'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Retention period in days (default: 90)'
        )
        parser.add_argument(
            '--action',
            type=str,
            default='archive',
            choices=['archive', 'delete', 'info'],
            help='Action to perform: archive, delete, or info (show what would be affected)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        days = options.get('days', 90)
        action = options.get('action', 'archive')
        dry_run = options.get('dry_run', False)
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get logs older than cutoff
        old_logs = ActivityLog.objects.filter(timestamp__lt=cutoff_date)
        old_notifications = Notification.objects.filter(created_at__lt=cutoff_date, read_at__isnull=False)
        
        log_count = old_logs.count()
        notification_count = old_notifications.count()
        
        if action == 'info':
            self.stdout.write(self.style.HTTP_INFO(f'Logs older than {days} days: {log_count}'))
            self.stdout.write(self.style.HTTP_INFO(f'Read notifications older than {days} days: {notification_count}'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN - Would affect {log_count} logs and {notification_count} notifications'))
        
        if action == 'delete':
            if dry_run:
                self.stdout.write(self.style.INFO(f'Would delete {log_count} activity logs'))
                self.stdout.write(self.style.INFO(f'Would delete {notification_count} old notifications'))
            else:
                # Delete old logs
                deleted_logs, _ = old_logs.delete()
                deleted_notifs, _ = old_notifications.delete()
                
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_logs} activity logs'))
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_notifs} old notifications'))
        
        elif action == 'archive':
            if dry_run:
                self.stdout.write(self.style.INFO(f'Would archive {log_count} activity logs (set is_archived=True)'))
            else:
                # Mark as archived instead of deleting
                archived_count = old_logs.update(is_archived=True)
                self.stdout.write(self.style.SUCCESS(f'Archived {archived_count} activity logs'))
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Audit retention policy applied: {days} days retention period'))


class RetentionSettings:
    """Settings for audit retention - can be configured in settings.py"""
    
    # Default retention period in days
    RETENTION_DAYS = 90
    
    # What to do with old logs: 'archive' or 'delete'
    RETENTION_ACTION = 'archive'
    
    # Also clean old read notifications
    CLEAN_NOTIFICATIONS = True
    NOTIFICATION_RETENTION_DAYS = 30