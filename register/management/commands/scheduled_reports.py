"""
Management command to generate and email scheduled reports
Run daily/weekly/monthly via cron
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from django.db.models import Count
from register.models import File, FileRequest, ActivityLog
from register.export_utils import export_files_to_csv, export_requests_to_csv


class Command(BaseCommand):
    help = 'Generate and email scheduled reports to administrators'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='daily',
            choices=['daily', 'weekly', 'monthly'],
            help='Type of report to generate'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without sending emails'
        )
        parser.add_argument(
            '--recipients',
            type=str,
            help='Comma-separated list of email recipients (overrides default)'
        )
    
    def handle(self, *args, **options):
        report_type = options.get('type', 'daily')
        dry_run = options.get('dry_run', False)
        recipients_override = options.get('recipients')
        
        # Determine date range
        now = timezone.now()
        if report_type == 'daily':
            start_date = now - timedelta(days=1)
            period = 'Daily'
        elif report_type == 'weekly':
            start_date = now - timedelta(weeks=1)
            period = 'Weekly'
        else:  # monthly
            start_date = now - timedelta(days=30)
            period = 'Monthly'
        
        # Get recipients
        if recipients_override:
            recipients = [r.strip() for r in recipients_override.split(',')]
        else:
            # Get admin emails
            from django.contrib.auth.models import User
            admins = User.objects.filter(
                is_superuser=True,
                email__isnull=False
            ).exclude(email='').values_list('email', flat=True)
            recipients = list(admins)
        
        if not recipients:
            self.stdout.write(self.style.WARNING('No recipients found. Use --recipients to specify.'))
            return
        
        # Generate report data
        report_data = self.generate_report_data(start_date, now, report_type)
        
        # Create email content
        subject = f'{period} File Tracking Report - {now.strftime("%Y-%m-%d")}'
        
        # Build HTML message
        html_content = self.build_html_report(report_data, period, start_date, now)
        
        if dry_run:
            self.stdout.write(self.style.HTTP_INFO(f'Would send report to: {recipients}'))
            self.stdout.write(self.style.HTTP_INFO(f'Subject: {subject}'))
            self.stdout.write(self.style.HTTP_INFO(f'Files: {report_data["files_created"]}'))
            self.stdout.write(self.style.HTTP_INFO(f'Requests: {report_data["requests_created"]}'))
        else:
            try:
                send_mail(
                    subject=subject,
                    message='Please view this email in an HTML-compatible client.',
                    html_message=html_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipients,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f'Report sent to {len(recipients)} recipients'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send email: {e}'))
    
    def generate_report_data(self, start_date, end_date, report_type):
        """Generate statistics for the report"""
        
        # File stats
        files_created = File.objects.filter(created_at__gte=start_date).count()
        files_checked_out = File.objects.filter(status='checked_out').count()
        files_overdue = File.objects.filter(status='overdue').count()
        
        # Request stats
        requests_created = FileRequest.objects.filter(created_at__gte=start_date).count()
        requests_approved = FileRequest.objects.filter(
            created_at__gte=start_date,
            status__in=['approved', 'ready_for_pickup', 'handed_over']
        ).count()
        requests_completed = FileRequest.objects.filter(
            created_at__gte=start_date,
            status__in=['confirmed', 'returned_verified']
        ).count()
        requests_completed = FileRequest.objects.filter(
            created_at__gte=start_date,
            status__in=['confirmed', 'returned_verified']
        ).count()
        
        # Activity stats
        downloads = ActivityLog.objects.filter(
            timestamp__gte=start_date,
            action='file_download'
        ).count()
        
        # Top departments by activity
        top_depts = FileRequest.objects.filter(
            created_at__gte=start_date
        ).values(
            'requesting_department__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return {
            'files_created': files_created,
            'files_checked_out': files_checked_out,
            'files_overdue': files_overdue,
            'requests_created': requests_created,
            'requests_approved': requests_approved,
            'requests_completed': requests_completed,
            'downloads': downloads,
            'top_departments': list(top_depts),
        }
    
    def build_html_report(self, data, period, start_date, end_date):
        """Build HTML report email"""
        from django.template.loader import render_to_string
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #0d6efd; color: white; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
                .stat {{ display: inline-block; margin: 10px 20px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #0d6efd; }}
                .stat-label {{ font-size: 12px; color: #6c757d; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #dee2e6; }}
                th {{ background: #e9ecef; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2 style="margin: 0;">{period} File Tracking Report</h2>
                <p style="margin: 5px 0;">{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="section">
                <h3>File Statistics</h3>
                <div class="stat">
                    <div class="stat-value">{data['files_created']}</div>
                    <div class="stat-label">Files Created</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{data['files_checked_out']}</div>
                    <div class="stat-label">Currently Checked Out</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{data['files_overdue']}</div>
                    <div class="stat-label">Overdue</div>
                </div>
            </div>
            
            <div class="section">
                <h3>Request Statistics</h3>
                <div class="stat">
                    <div class="stat-value">{data['requests_created']}</div>
                    <div class="stat-label">Requests Created</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{data['requests_approved']}</div>
                    <div class="stat-label">Approved</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{data['requests_completed']}</div>
                    <div class="stat-label">Completed</div>
                </div>
            </div>
            
            <div class="section">
                <h3>Activity</h3>
                <div class="stat">
                    <div class="stat-value">{data['downloads']}</div>
                    <div class="stat-label">File Downloads</div>
                </div>
            </div>
            
            <div class="section">
                <h3>Top Departments</h3>
                <table>
                    <tr><th>Department</th><th>Requests</th></tr>
        """
        
        for dept in data['top_departments']:
            html += f"""
                    <tr>
                        <td>{dept['requesting_department__name'] or 'N/A'}</td>
                        <td>{dept['count']}</td>
                    </tr>
            """
        
        html += """
                </table>
            </div>
            
            <p style="color: #6c757d; font-size: 12px; margin-top: 30px;">
                Generated by File Tracking System
            </p>
        </body>
        </html>
        """
        
        return html