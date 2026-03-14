"""
Management command to check and notify about overdue files
Run daily with cron or task scheduler
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from register.models import File
from register.emails import send_overdue_notification


class Command(BaseCommand):
    help = 'Check for overdue files and send email notifications'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be notified without sending emails',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        # Find files that are checked out and past due date
        overdue_files = File.objects.filter(
            status='checked_out',
            due_date__lt=timezone.now()
        )
        
        total_notifications = 0
        
        for file in overdue_files:
            # Mark as overdue in system
            file.status = 'overdue'
            file.save()
            
            if file.current_holder:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would notify {file.current_holder.email} '
                            f'about overdue file {file.reference}'
                        )
                    )
                else:
                    try:
                        sent = send_overdue_notification(file, file.current_holder)
                        if sent:
                            total_notifications += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Sent overdue notification for {file.reference}'
                                )
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Failed to send email for {file.reference}: {e}'
                            )
                        )
        
        # Also find files that are already overdue but not yet notified
        already_overdue = File.objects.filter(
            status='overdue',
            due_date__lt=timezone.now()
        ).exclude(
            # Exclude files marked today
            updated_at__date=timezone.now().date()
        )
        
        for file in already_overdue:
            if file.current_holder and file.current_holder.email:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would send reminder to {file.current_holder.email} '
                            f'for overdue file {file.reference}'
                        )
                    )
                else:
                    try:
                        sent = send_overdue_notification(file, file.current_holder)
                        if sent:
                            total_notifications += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Failed: {e}')
                        )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Dry run complete. Would send {total_notifications} notifications.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Overdue check complete. Sent {total_notifications} notifications.'
                )
            )
