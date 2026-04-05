"""
Management command to bulk import files from CSV/Excel
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from register.models import Department, File, FileTag
import csv
import io


class Command(BaseCommand):
    help = 'Bulk import files from CSV file'
    
    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--department',
            type=str,
            help='Default department code (if not in CSV)'
        )
        parser.add_argument(
            '--created-by',
            type=str,
            help='Username of user creating files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without creating files'
        )
        parser.add_argument(
            '--skip-errors',
            action='store_true',
            help='Skip rows with errors instead of stopping'
        )
    
    def handle(self, *args, **options):
        file_path = options.get('file')
        default_dept = options.get('department')
        created_by_username = options.get('created_by')
        dry_run = options.get('dry_run', False)
        skip_errors = options.get('skip_errors', False)
        
        # Get user
        if created_by_username:
            try:
                created_by = User.objects.get(username=created_by_username)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"User '{created_by_username}' not found"))
                return
        else:
            created_by = User.objects.filter(is_superuser=True).first()
            if not created_by:
                self.stderr.write(self.style.ERROR("No superuser found to assign as creator"))
                return
        
        # Read CSV
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading file: {e}"))
            return
        
        if not rows:
            self.stderr.write(self.style.WARNING("No data found in CSV file"))
            return
        
        self.stdout.write(f"Found {len(rows)} rows to import")
        
        # Validate and import
        errors = []
        successful = 0
        
        for idx, row in enumerate(rows, 1):
            try:
                # Extract fields - adjust based on your CSV format
                title = row.get('title', '').strip()
                reference = row.get('reference', '').strip()
                description = row.get('description', '').strip()
                department_code = row.get('department', '').strip() or default_dept
                
                if not title:
                    errors.append(f"Row {idx}: Title is required")
                    if not skip_errors:
                        continue
                
                # Get department
                if department_code:
                    try:
                        department = Department.objects.get(code=department_code)
                    except Department.DoesNotExist:
                        errors.append(f"Row {idx}: Department '{department_code}' not found")
                        if not skip_errors:
                            continue
                else:
                    department = None
                
                if dry_run:
                    self.stdout.write(f"DRY RUN: Would create file '{title}' ({reference})")
                    successful += 1
                else:
                    with transaction.atomic():
                        # Generate reference if not provided
                        if not reference:
                            reference = self._generate_reference(department)
                        
                        file = File.objects.create(
                            title=title,
                            reference=reference,
                            description=description,
                            department=department,
                            created_by=created_by,
                            status='in_registry'
                        )
                        
                        # Handle tags if present
                        tags = row.get('tags', '').strip()
                        if tags:
                            tag_list = [t.strip() for t in tags.split(',')]
                            for tag_name in tag_list:
                                tag, _ = FileTag.objects.get_or_create(name=tag_name)
                                file.tags.add(tag)
                        
                        # Generate QR code if requested
                        if row.get('generate_qr', '').lower() == 'yes':
                            file.generate_qr_code()
                        
                        self.stdout.write(f"Created: {file.reference} - {file.title}")
                    
                    successful += 1
                    
            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")
                if not skip_errors:
                    self.stdout.write(self.style.ERROR(f"Row {idx}: {e}"))
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f"\nImport complete: {successful} files"))
        if errors:
            self.stdout.write(self.style.ERROR(f"Errors: {len(errors)}"))
            for error in errors[:10]:  # Show first 10 errors
                self.stdout.write(f"  - {error}")
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more errors")
    
    def _generate_reference(self, department):
        """Generate a unique file reference"""
        import random
        from datetime import datetime
        
        year = datetime.now().year
        prefix = department.code if department else 'GEN'
        
        # Get max sequence for this department/year
        max_seq = File.objects.filter(
            department=department,
            reference__startswith=f"{prefix}/{year}/"
        ).count()
        
        sequence = max_seq + 1
        return f"{prefix}/{year}/{sequence:04d}"