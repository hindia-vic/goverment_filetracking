"""
Django management command to verify and maintain audit trail integrity
"""
from django.core.management.base import BaseCommand
from register.models import ActivityLog
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verify and maintain audit trail integrity'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify integrity of all log entries'
        )
        parser.add_argument(
            '--hash-existing',
            action='store_true',
            help='Generate hashes for existing entries without hashes'
        )
        parser.add_argument(
            '--fix-chain',
            action='store_true',
            help='Fix hash chain for all entries'
        )
        parser.add_argument(
            '--export',
            action='store_true',
            help='Export audit log to JSON for external verification'
        )
    
    def handle(self, *args, **options):
        if options['verify']:
            self.verify_integrity()
        elif options['hash_existing']:
            self.hash_existing()
        elif options['fix_chain']:
            self.fix_chain()
        elif options['export']:
            self.export_audit()
        else:
            self.stdout.write(self.style.WARNING('No option specified. Use --help for options.'))
    
    def verify_integrity(self):
        """Verify integrity of all log entries"""
        self.stdout.write('Verifying audit trail integrity...')
        
        total = ActivityLog.objects.count()
        valid = 0
        invalid = 0
        
        for log in ActivityLog.objects.all().order_by('timestamp'):
            if log.verify_integrity():
                valid += 1
            else:
                invalid += 1
                self.stdout.write(self.style.ERROR(f'Invalid entry at {log.timestamp}'))
        
        self.stdout.write(f'Results: {valid}/{total} valid, {invalid} invalid')
        
        # Verify chain
        latest = ActivityLog.objects.order_by('-timestamp').first()
        if latest:
            is_valid, msg = latest.verify_chain()
            if is_valid:
                self.stdout.write(self.style.SUCCESS('Chain integrity: VALID'))
            else:
                self.stdout.write(self.style.ERROR(f'Chain integrity: {msg}'))
    
    def hash_existing(self):
        """Generate hashes for existing entries without hashes"""
        self.stdout.write('Generating hashes for existing entries...')
        
        count = 0
        for log in ActivityLog.objects.filter(entry_hash='').order_by('timestamp'):
            log._generate_hash()
            log._skip_immutability = True  # Allow bulk update
            log.save(update_fields=['entry_hash', 'previous_hash', 'checksum'])
            count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Generated hashes for {count} entries'))
    
    def fix_chain(self):
        """Fix hash chain for all entries"""
        self.stdout.write('Fixing hash chain...')
        
        previous_hash = 'genesis'
        count = 0
        
        for log in ActivityLog.objects.order_by('timestamp'):
            if log.previous_hash != previous_hash:
                log.previous_hash = previous_hash
                log._generate_hash()
                log._skip_immutability = True  # Allow bulk update
                log.save(update_fields=['entry_hash', 'previous_hash', 'checksum'])
                count += 1
            previous_hash = log.entry_hash
        
        self.stdout.write(self.style.SUCCESS(f'Fixed chain for {count} entries'))
    
    def export_audit(self):
        """Export audit log to JSON for external verification"""
        import json
        from django.http import HttpResponse
        
        self.stdout.write('Exporting audit log...')
        
        logs = ActivityLog.objects.all().order_by('timestamp').values(
            'id', 'user__username', 'action', 'description', 
            'ip_address', 'timestamp', 'entry_hash', 'previous_hash',
            'checksum', 'subsystem', 'severity'
        )
        
        output = []
        for log in logs:
            output.append({
                'id': log['id'],
                'user': log['user__username'],
                'action': log['action'],
                'description': log['description'],
                'ip_address': log['ip_address'],
                'timestamp': log['timestamp'].isoformat() if log['timestamp'] else None,
                'entry_hash': log['entry_hash'],
                'previous_hash': log['previous_hash'],
                'checksum': log['checksum'],
                'subsystem': log['subsystem'],
                'severity': log['severity'],
            })
        
        # Write to file
        filename = f'audit_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        self.stdout.write(self.style.SUCCESS(f'Exported to {filename}'))
        self.stdout.write(f'Total entries: {len(output)}')