"""
Management command to check system health and generate reports
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from register.models import File, FileRequest, ActivityLog, Notification


class Command(BaseCommand):
    help = 'Run system health checks and generate status report'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--details',
            action='store_true',
            help='Show detailed output',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON for programmatic use',
        )
    
    def handle(self, *args, **options):
        details = options.get('details', False)
        output_json = options.get('json', False)
        
        report = self.generate_report(details)
        
        if output_json:
            import json
            print(json.dumps(report, indent=2))
        else:
            self.print_report(report)
    
    def generate_report(self, verbose):
        """Generate system health report"""
        now = timezone.now()
        
        # File statistics
        file_stats = {
            'total': File.objects.count(),
            'in_registry': File.objects.filter(status='in_registry').count(),
            'checked_out': File.objects.filter(status='checked_out').count(),
            'overdue': File.objects.filter(status='overdue').count(),
            'archived': File.objects.filter(status='archived').count(),
        }
        
        # Request statistics
        request_stats = {
            'total': FileRequest.objects.count(),
            'pending': FileRequest.objects.filter(status='pending').count(),
            'approved': FileRequest.objects.filter(status='approved').count(),
            'checked_out_active': FileRequest.objects.filter(
                status__in=['confirmed', 'handed_over']
            ).count(),
            'pending_return': FileRequest.objects.filter(status='pending_return').count(),
            'returned_verified': FileRequest.objects.filter(status='returned_verified').count(),
        }
        
        # Overdue files
        overdue_files = File.objects.filter(
            status__in=['checked_out', 'overdue'],
            due_date__lt=now
        ).values('title', 'current_holder__username', 'due_date', 'department__code', 'sequence', 'year')
        
        overdue_list = []
        for f in overdue_files:
            # Construct reference from department code, year, and sequence
            ref = f"{f['department__code']}/{f['year']}/{f['sequence']:04d}"
            overdue_list.append({
                'reference': ref,
                'title': f['title'],
                'holder': f['current_holder__username'],
                'due_date': str(f['due_date']),
            })
        
        # Recent activity (last 7 days)
        week_ago = now - timedelta(days=7)
        activity_stats = ActivityLog.objects.filter(
            timestamp__gte=week_ago
        ).values('action').annotate(count=Count('action'))
        
        activity_by_action = {item['action']: item['count'] for item in activity_stats}
        
        # Unread notifications (use read_at field - null means unread)
        unread_notifications = Notification.objects.filter(
            recipient__is_active=True,
            read_at__isnull=True
        ).count()
        
        # Database size estimate
        from django.db import connection
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                db_size = cursor.fetchone()[0]
            except:
                db_size = "Unknown"
        
        report = {
            'generated_at': str(now),
            'file_statistics': file_stats,
            'request_statistics': request_stats,
            'overdue_files': overdue_list,
            'overdue_count': len(overdue_list),
            'activity_last_7_days': activity_by_action,
            'unread_notifications': unread_notifications,
            'database_size': db_size,
        }
        
        return report
    
    def print_report(self, report):
        """Print human-readable report"""
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write(self.style.HTTP_INFO("  FILE TRACKING SYSTEM - HEALTH REPORT"))
        self.stdout.write(self.style.HTTP_INFO("=" * 60))
        self.stdout.write("")
        
        self.stdout.write(self.style.HTTP_INFO("FILE STATISTICS"))
        self.stdout.write("-" * 40)
        for key, value in report['file_statistics'].items():
            self.stdout.write(f"  {key.replace('_', ' ').title()}: {value}")
        self.stdout.write("")
        
        self.stdout.write(self.style.HTTP_INFO("REQUEST STATISTICS"))
        self.stdout.write("-" * 40)
        for key, value in report['request_statistics'].items():
            self.stdout.write(f"  {key.replace('_', ' ').title()}: {value}")
        self.stdout.write("")
        
        self.stdout.write(self.style.HTTP_INFO("OVERDUE FILES"))
        self.stdout.write("-" * 40)
        if report['overdue_count'] > 0:
            for f in report['overdue_files']:
                self.stdout.write(
                    f"  {f['reference']} - {f['title']} (by {f['holder']})"
                )
        else:
            self.stdout.write("  No overdue files")
        self.stdout.write("")
        
        self.stdout.write(self.style.HTTP_INFO("ACTIVITY (LAST 7 DAYS)"))
        self.stdout.write("-" * 40)
        for action, count in report['activity_last_7_days'].items():
            self.stdout.write(f"  {action}: {count}")
        if not report['activity_last_7_days']:
            self.stdout.write("  No activity")
        self.stdout.write("")
        
        self.stdout.write(self.style.HTTP_INFO("SYSTEM INFO"))
        self.stdout.write("-" * 40)
        self.stdout.write(f"  Unread Notifications: {report['unread_notifications']}")
        self.stdout.write(f"  Database Size: {report['database_size']}")
        self.stdout.write(f"  Report Generated: {report['generated_at']}")
        self.stdout.write("")