"""
Management command to send automatic reminders for due dates and overdue files
Run daily via cron or Windows Task Scheduler
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.db.models import Q
from register.models import File, FileRequest
from register.emails import send_overdue_notification


class Command(BaseCommand):
    help = 'Send automatic reminders for due dates and overdue files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--due-days',
            type=int,
            default=3,
            help='Send reminder for files due in X days (default: 3)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without sending emails'
        )
        parser.add_argument(
            '--email-type',
            type=str,
            default='all',
            choices=['all', 'due', 'overdue'],
            help='Type of emails to send: all, due (upcoming), or overdue'
        )
    
    def handle(self, *args, **options):
        due_days = options.get('due_days', 3)
        dry_run = options.get('dry_run', False)
        email_type = options.get('email_type', 'all')
        
        now = timezone.now()
        
        # 1. Remind users with files due soon
        if email_type in ['all', 'due']:
            due_soon = File.objects.filter(
                status='checked_out',
                due_date__gte=now,
                due_date__lte=now + timedelta(days=due_days)
            ).select_related('current_holder', 'department')
            
            for file in due_soon:
                if file.current_holder and file.current_holder.email:
                    if dry_run:
                        self.stdout.write(f"Would send due reminder to {file.current_holder.email} for {file.reference}")
                    else:
                        try:
                            days_left = (file.due_date - now).days
                            send_mail(
                                subject=f"File Due Soon - {file.reference}",
                                message=f"""
Dear {file.current_holder.get_full_name()},

This is a reminder that the file "{file.title}" ({file.reference}) is due to be returned in {days_left} day(s).

Due Date: {file.due_date.strftime('%Y-%m-%d')}
Department: {file.department.name if file.department else 'N/A'}

Please return the file to the registry before the due date to avoid overdue penalties.

Best regards,
File Tracking System
                                """,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[file.current_holder.email],
                                fail_silently=True
                            )
                            self.stdout.write(f"Sent due reminder for {file.reference} to {file.current_holder.email}")
                        except Exception as e:
                            self.stdout.write(f"Error sending to {file.current_holder.email}: {e}")
        
        # 2. Send overdue notifications
        if email_type in ['all', 'overdue']:
            overdue_files = File.objects.filter(
                status__in=['checked_out', 'overdue'],
                due_date__lt=now
            ).select_related('current_holder', 'department')
            
            for file in overdue_files:
                if file.current_holder and file.current_holder.email:
                    days_overdue = (now - file.due_date).days
                    
                    if dry_run:
                        self.stdout.write(f"Would send overdue notice to {file.current_holder.email} for {file.reference} (overdue {days_overdue} days)")
                    else:
                        try:
                            send_mail(
                                subject=f"OVERDUE: File {file.reference}",
                                message=f"""
Dear {file.current_holder.get_full_name()},

The file "{file.title}" ({file.reference}) is now OVERDUE.

Original Due Date: {file.due_date.strftime('%Y-%m-%d')}
Days Overdue: {days_overdue}
Department: {file.department.name if file.department else 'N/A'}

Please return the file to the registry immediately to avoid further penalties.

Contact the registry for assistance.

Best regards,
File Tracking System
                                """,
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[file.current_holder.email],
                                fail_silently=True
                            )
                            
                            # Update status to overdue
                            file.status = 'overdue'
                            file.save()
                            
                            # Also notify admins
                            admins = User.objects.filter(
                                is_superuser=True,
                                email__isnull=False
                            ).exclude(email='')
                            
                            for admin in admins:
                                send_mail(
                                    subject=f"File Overdue Alert - {file.reference}",
                                    message=f"""
The file "{file.title}" ({file.reference}) is now overdue.

User: {file.current_holder.get_full_name()} ({file.current_holder.username})
Due Date: {file.due_date.strftime('%Y-%m-%d')}
Days Overdue: {days_overdue}

This is an automated notification.
                                    """,
                                    from_email=settings.DEFAULT_FROM_EMAIL,
                                    recipient_list=[admin.email],
                                    fail_silently=True
                                )
                            
                            self.stdout.write(f"Sent overdue notice for {file.reference}")
                            
                        except Exception as e:
                            self.stdout.write(f"Error sending overdue notice: {e}")
        
        # 3. Notify registry about pending returns
        pending_returns = FileRequest.objects.filter(
            status='pending_return',
            created_at__lt=now - timedelta(days=1)
        ).select_related('file', 'requesting_user')
        
        if pending_returns.exists():
            registries = User.objects.filter(
                profile__role='registry',
                email__isnull=False
            ).exclude(email='')
            
            return_count = pending_returns.count()
            
            for registry in registries:
                if dry_run:
                    self.stdout.write(f"Would notify {registry.email} about {return_count} pending returns")
                else:
                    try:
                        send_mail(
                            subject=f"Pending File Returns - {return_count} files",
                            message=f"""
Dear Registry Officer,

There are {return_count} file return(s) awaiting verification.

Please review and verify the returns at your earliest convenience.

This is an automated notification from the File Tracking System.
                            """,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[registry.email],
                            fail_silently=True
                        )
                    except Exception as e:
                        pass
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS("Auto-reminders completed"))
        else:
            self.stdout.write(self.style.SUCCESS("Dry run complete - no emails sent"))


# Import User at module level for the notification
from django.contrib.auth.models import User