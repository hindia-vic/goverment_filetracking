import uuid
import qrcode
from io import BytesIO
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from PIL import Image


class UserProfile(models.Model):
    """Extended user profile with role management"""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('registry', 'Registry Officer'),
        ('department_user', 'Department User'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='department_user')
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['user__username']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    @property
    def is_admin(self):
        return self.role == 'admin' or self.user.is_superuser
    
    @property
    def is_registry(self):
        return self.role == 'registry'
    
    @property
    def is_department_user(self):
        return self.role == 'department_user'


class Notification(models.Model):
    """Notification system for file checkout requests"""
    NOTIFICATION_TYPES = [
        ('checkout_request', 'Checkout Request'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('file_handed', 'File Handed to User'),
        ('user_confirmed', 'User Confirmed Receipt'),
        ('checkout_approved', 'Checkout Approved'),
    ]
    
    NOTIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('read', 'Read'),
    ]
    
    file = models.ForeignKey('File', on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notifications_sent')
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=NOTIFICATION_STATUS, default='pending')
    
    # Related to checkout request workflow
    is_approved = models.BooleanField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    pickup_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.file.reference}"
    
    def mark_as_read(self):
        self.status = 'read'
        self.read_at = timezone.now()
        self.save()


class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class FileRequest(models.Model):
    """Track file checkout requests with approval workflow"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('handed_over', 'Handed Over'),
        ('confirmed', 'Confirmed by User'),
        ('cancelled', 'Cancelled'),
    ]
    
    file = models.ForeignKey('File', on_delete=models.CASCADE, related_name='checkout_requests')
    requesting_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_requests')
    requesting_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='file_requests')
    
    purpose = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Registry response
    pickup_date = models.DateTimeField(null=True, blank=True)
    registry_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_requests')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # User confirmation
    user_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    user_confirmation_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Request #{self.id} - {self.file.reference} by {self.requesting_user.username}"
    
    def approve(self, processed_by, pickup_date=None, notes=''):
        self.status = 'ready_for_pickup'
        self.processed_by = processed_by
        self.processed_at = timezone.now()
        self.pickup_date = pickup_date
        self.registry_notes = notes
        self.save()
        
        # Send in-app notification to user
        Notification.objects.create(
            file=self.file,
            recipient=self.requesting_user,
            sender=processed_by,
            notification_type='ready_for_pickup',
            title=f'File Ready for Pickup - {self.file.reference}',
            message=f'Your request for file {self.file.reference} has been approved. ' +
                    (f'Please pick up on {pickup_date.strftime("%Y-%m-%d")}.' if pickup_date else 'Please come to registry to collect.'),
            pickup_date=pickup_date
        )
        
        # Send email notification
        try:
            from register.emails import send_request_approval_notification
            send_request_approval_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    def reject(self, processed_by, reason=''):
        self.status = 'rejected'
        self.processed_by = processed_by
        self.processed_at = timezone.now()
        self.registry_notes = reason
        self.save()
        
        # Send in-app notification to user
        Notification.objects.create(
            file=self.file,
            recipient=self.requesting_user,
            sender=processed_by,
            notification_type='checkout_request',
            title=f'Request Rejected - {self.file.reference}',
            message=f'Your request for file {self.file.reference} has been rejected. Reason: {reason}'
        )
        
        # Send email notification
        try:
            from register.emails import send_request_rejection_notification
            send_request_rejection_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    def mark_handed_over(self, processed_by, notes=''):
        self.status = 'handed_over'
        self.processed_by = processed_by
        self.processed_at = timezone.now()
        self.registry_notes = notes
        self.save()
        
        # Send in-app notification to user to confirm
        Notification.objects.create(
            file=self.file,
            recipient=self.requesting_user,
            sender=processed_by,
            notification_type='file_handed',
            title=f'File Handed Over - {self.file.reference}',
            message=f'You have received file {self.file.reference}. Please confirm receipt.',
        )
        
        # Send email notification
        try:
            from register.emails import send_file_handover_notification
            send_file_handover_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    def confirm_receipt(self, notes=''):
        self.status = 'confirmed'
        self.user_confirmed = True
        self.confirmed_at = timezone.now()
        self.user_confirmation_notes = notes
        self.save()
        
        # Send notification to registry
        if self.processed_by:
            Notification.objects.create(
                file=self.file,
                recipient=self.processed_by,
                sender=self.requesting_user,
                notification_type='user_confirmed',
                title=f'User Confirmed Receipt - {self.file.reference}',
                message=f'{self.requesting_user.get_full_name()} has confirmed receipt of file {self.file.reference}.'
            )


class File(models.Model):
    STATUS_CHOICES = [
        ('in_registry', 'In Registry'),
        ('checked_out', 'Checked Out'),
        ('overdue', 'Overdue'),
        ('archived', 'Archived'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Reference number: HR/2026/004 format
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='files')
    year = models.IntegerField(default=timezone.now().year)
    sequence = models.PositiveIntegerField()
    
    # Unique identifier
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # File details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_registry')
    
    # Physical location tracking
    current_holder = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='held_files'
    )
    current_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_files'
    )
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    
    # QR Code
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    # Audit
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_files')
    
    # Archive fields
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='archived_files')
    archive_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['department', 'year', 'sequence']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['uuid']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-generate sequence if not set
        if not self.sequence:
            last_file = File.objects.filter(
                department=self.department,
                year=self.year
            ).order_by('-sequence').first()
            self.sequence = (last_file.sequence + 1) if last_file else 1
        
        super().save(*args, **kwargs)
        
        # Generate QR code if not exists
        if not self.qr_code:
            self.generate_qr_code()
    
    def generate_qr_code(self):
        """Generate QR code containing file reference"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(str(self.uuid))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Save to model
        filename = f'file_{self.reference.replace("/", "_")}.png'
        self.qr_code.save(filename, buffer, save=False)
        self.save(update_fields=['qr_code'])
    
    @property
    def reference(self):
        """Returns formatted reference: HR/2026/004"""
        return f"{self.department.code}/{self.year}/{self.sequence:04d}"
    
    def check_out(self, user, department, notes=''):
        """Check out file to a user"""
        self.status = 'checked_out'
        self.current_holder = user
        self.current_department = department
        self.checked_out_at = timezone.now()
        self.due_date = timezone.now() + timezone.timedelta(days=7)
        self.save()
        
        # Create movement record
        FileMovement.objects.create(
            file=self,
            action='checkout',
            from_user=self.created_by,
            to_user=user,
            from_department=self.department,
            to_department=department,
            notes=notes
        )
    
    def check_in(self, user, notes=''):
        """Return file to registry"""
        previous_holder = self.current_holder
        previous_dept = self.current_department
        
        self.status = 'in_registry'
        self.current_holder = None
        self.current_department = None
        self.checked_out_at = None
        self.due_date = None
        self.save()
        
        # Create movement record
        FileMovement.objects.create(
            file=self,
            action='checkin',
            from_user=previous_holder,
            to_user=user,
            from_department=previous_dept,
            to_department=self.department,
            notes=notes
        )
    
    def mark_overdue(self):
        """Mark file as overdue"""
        if self.status == 'checked_out' and self.due_date and timezone.now() > self.due_date:
            self.status = 'overdue'
            self.save()
            return True
        return False
    
    def is_overdue(self):
        """Check if file is overdue"""
        if self.status == 'checked_out' and self.due_date:
            return timezone.now() > self.due_date
        return False
    
    def get_absolute_url(self):
        return reverse('file_detail', kwargs={'uuid': self.uuid})
    
    def archive(self, user, reason=''):
        """Archive the file"""
        if self.status not in ['in_registry', 'archived']:
            return False, "Cannot archive a file that is currently checked out"
        
        self.status = 'archived'
        self.archived_at = timezone.now()
        self.archived_by = user
        self.archive_reason = reason
        self.save()
        
        # Create version snapshot
        FileVersion.objects.create(
            file=self,
            version_number=1,
            title=self.title,
            description=self.description,
            department=self.department,
            created_by=self.created_by,
            change_type='archive',
            notes=f'Archived: {reason}'
        )
        return True, "File archived successfully"
    
    def restore_from_archive(self, user):
        """Restore file from archive"""
        if self.status != 'archived':
            return False, "File is not archived"
        
        self.status = 'in_registry'
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = ''
        self.save()
        return True, "File restored successfully"
    
    def create_version(self, user, change_type='update', notes=''):
        """Create a version snapshot of the file"""
        last_version = self.versions.first()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        FileVersion.objects.create(
            file=self,
            version_number=version_number,
            title=self.title,
            description=self.description,
            department=self.department,
            created_by=user,
            change_type=change_type,
            notes=notes
        )
    
    def __str__(self):
        return f"{self.reference} - {self.title}"


class FileVersion(models.Model):
    """Track file versions and changes"""
    CHANGE_TYPES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('archive', 'Archived'),
        ('restore', 'Restored'),
    ]
    
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-version_number']
        verbose_name = 'File Version'
        verbose_name_plural = 'File Versions'
        unique_together = ['file', 'version_number']
    
    def __str__(self):
        return f"{self.file.reference} - v{self.version_number}"


class FileMovement(models.Model):
    ACTION_CHOICES = [
        ('checkout', 'Checked Out'),
        ('checkin', 'Returned'),
        ('transfer', 'Transferred'),
        ('audit', 'Audit Note'),
    ]
    
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='movements')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Chain of custody
    from_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='movements_from')
    to_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='movements_to')
    from_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='movements_from')
    to_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='movements_to')
    
    # Digital signature simulation (in production, use proper digital signature)
    signature_data = models.TextField(blank=True, help_text="Digital signature or confirmation code")
    signed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'File Movement'
        verbose_name_plural = 'File Movements'
    
    def __str__(self):
        return f"{self.file.reference} - {self.get_action_display()} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class AuditLog(models.Model):
    """Additional audit trail for system actions"""
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)


class ActivityLog(models.Model):
    """Track user activities across the system"""
    ACTION_TYPES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('password_reset', 'Password Reset'),
        ('profile_update', 'Profile Updated'),
        ('file_view', 'Viewed File'),
        ('file_upload', 'Uploaded File'),
        ('file_checkout', 'Checked Out File'),
        ('file_checkin', 'Returned File'),
        ('file_request', 'Requested File'),
        ('request_approve', 'Approved Request'),
        ('request_reject', 'Rejected Request'),
        ('request_handover', 'Handed Over File'),
        ('user_create', 'Created User'),
        ('user_update', 'Updated User'),
        ('department_create', 'Created Department'),
        ('department_update', 'Updated Department'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=30, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# Create your models here.
