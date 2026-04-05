"""
Export utilities for CSV and Excel exports
"""
import csv
import io
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime


class ExportMixin:
    """Mixin to add export functionality to views"""
    
    def export_csv(self, queryset, fields, filename='export.csv'):
        """
        Export queryset to CSV
        
        Args:
            queryset: Django queryset to export
            fields: List of field names or (field, header) tuples
            filename: Name of the export file
        """
        # Handle both simple field names and (field, header) tuples
        if fields and isinstance(fields[0], tuple):
            headers = [f[1] for f in fields]
            field_names = [f[0] for f in fields]
        else:
            headers = [f.replace('_', ' ').title() for f in fields]
            field_names = fields
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(headers)
        
        # Write data rows
        for obj in queryset:
            row = []
            for field in field_names:
                value = self._get_nested_value(obj, field)
                # Handle special types
                if hasattr(value, 'strftime'):  # datetime/date
                    value = value.strftime('%Y-%m-%d %H:%M')
                elif hasattr(value, '__iter__') and not isinstance(value, str):
                    value = ', '.join(str(v) for v in value)
                else:
                    value = str(value) if value is not None else ''
                row.append(value)
            writer.writerow(row)
        
        # Return response
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    def _get_nested_value(self, obj, field):
        """Get value from object, handling nested attributes"""
        parts = field.split('__')
        value = obj
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict):
                value = value.get(part, '')
            else:
                return ''
            # Handle callable
            if callable(value):
                value = value()
        return value


def export_files_to_csv(files):
    """Export file list to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Reference', 'Title', 'Department', 'Status', 'Current Holder', 'Priority', 'Created At', 'Due Date'])
    
    # Data
    for f in files:
        writer.writerow([
            f.reference,
            f.title,
            f.department.code if f.department else '',
            f.get_status_display(),
            f.current_holder.get_full_name() if f.current_holder else 'In Registry',
            f.get_priority_display(),
            f.created_at.strftime('%Y-%m-%d') if f.created_at else '',
            f.due_date.strftime('%Y-%m-%d') if f.due_date else '',
        ])
    
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="files_export_{timezone.now().strftime("%Y%m%d")}.csv"'
    return response


def export_requests_to_csv(requests):
    """Export file request list to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Request ID', 'File Reference', 'File Title', 'Requested By', 'Department', 'Status', 'Purpose', 'Created At'])
    
    # Data
    for r in requests:
        writer.writerow([
            r.id,
            r.file.reference if r.file else '',
            r.file.title if r.file else '',
            r.requesting_user.get_full_name() if r.requesting_user else '',
            r.requesting_department.name if r.requesting_department else '',
            r.get_status_display(),
            r.purpose,
            r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
        ])
    
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="requests_export_{timezone.now().strftime("%Y%m%d")}.csv"'
    return response


def export_activity_to_csv(activities):
    """Export activity log to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['User', 'Action', 'Description', 'IP Address', 'Timestamp'])
    
    # Data
    for a in activities:
        writer.writerow([
            a.user.get_full_name() if a.user else 'System',
            a.action,
            a.description,
            a.ip_address or '',
            a.timestamp.strftime('%Y-%m-%d %H:%M') if a.timestamp else '',
        ])
    
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="activity_export_{timezone.now().strftime("%Y%m%d")}.csv"'
    return response


def export_users_to_csv(users):
    """Export user list to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Username', 'Full Name', 'Email', 'Department', 'Role', 'Is Active', 'Date Joined'])
    
    # Data
    for u in users:
        writer.writerow([
            u.username,
            u.get_full_name(),
            u.email,
            u.profile.department.name if hasattr(u, 'profile') and u.profile.department else '',
            u.profile.get_role_display() if hasattr(u, 'profile') else '',
            'Yes' if u.is_active else 'No',
            u.date_joined.strftime('%Y-%m-%d') if u.date_joined else '',
        ])
    
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d")}.csv"'
    return response


def export_movements_to_csv(movements):
    """Export file movements to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['File Reference', 'Action', 'From User', 'To User', 'From Dept', 'To Dept', 'Notes', 'Timestamp'])
    
    # Data
    for m in movements:
        writer.writerow([
            m.file.reference if m.file else '',
            m.get_action_display(),
            m.from_user.get_full_name() if m.from_user else '',
            m.to_user.get_full_name() if m.to_user else '',
            m.from_department.name if m.from_department else '',
            m.to_department.name if m.to_department else '',
            m.notes or '',
            m.timestamp.strftime('%Y-%m-%d %H:%M') if m.timestamp else '',
        ])
    
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="movements_export_{timezone.now().strftime("%Y%m%d")}.csv"'
    return response