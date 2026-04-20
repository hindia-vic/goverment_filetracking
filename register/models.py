import uuid
import qrcode
import hashlib
import os
from io import BytesIO
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from PIL import Image


# Add default function before the DigitalSignature model
def get_default_expiry():
    return timezone.now() + timezone.timedelta(days=365)


class DigitalSignature(models.Model):
    """Digital signatures for legally auditable approvals"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='digital_signature')
    
    # Key pair storage (encrypted)
    public_key = models.TextField(help_text="PEM-encoded public key")
    private_key_encrypted = models.TextField(help_text="Encrypted PEM-encoded private key")
    key_fingerprint = models.CharField(max_length=64, unique=True, help_text="SHA-256 fingerprint of public key")
    
    # Certificate info
    certificate_serial = models.CharField(max_length=64, unique=True, help_text="Certificate serial number")
    certificate_not_before = models.DateTimeField(default=timezone.now)
    certificate_not_after = models.DateTimeField(default=get_default_expiry)
    
    # Key derivation
    salt = models.CharField(max_length=32, help_text="Salt for key derivation")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_revoked = models.BooleanField(default=False)
    revocation_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Signature for {self.user.username} (valid until {self.certificate_not_after.date()})"
    
    def is_valid(self):
        """Check if signature is currently valid"""
        now = timezone.now()
        return (self.is_active and not self.is_revoked and
                self.certificate_not_before <= now <= self.certificate_not_after)
    
    def sign(self, data):
        """Sign data with user's private key"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
        
        if not self.is_valid():
            raise ValueError("Digital signature is not valid")
        
        # Decrypt private key (would need user's password in real implementation)
        private_key = self._decrypt_private_key()
        
        # Sign the data
        data_hash = hashlib.sha256(str(data).encode()).hexdigest()
        
        signature = private_key.sign(
            data_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature.hex()
    
    def verify(self, data, signature_hex):
        """Verify a signature"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        try:
            signature = bytes.fromhex(signature_hex)
            data_hash = hashlib.sha256(str(data).encode()).hexdigest()
            
            public_key = serialization.load_pem_public_key(
                self.public_key.encode(),
                backend=default_backend()
            )
            
            public_key.verify(
                signature,
                data_hash.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
    
    def _decrypt_private_key(self):
        """Decrypt private key (simplified - would need password in production)"""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import base64
        
        # In production, this would require user's password
        key_data = base64.b64decode(self.private_key_encrypted)
        
        return serialization.load_pem_private_key(
            key_data,
            password=None,
            backend=default_backend()
        )


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
    
    @property
    def notification_preferences(self):
        """Get notification preferences for this user"""
        prefs, created = NotificationPreferences.objects.get_or_create(user=self.user)
        return prefs


class NotificationPreferences(models.Model):
    """User notification preferences"""
    
    NOTIFICATION_TYPES = [
        ('email_request_approved', 'Email - Request Approved'),
        ('email_request_rejected', 'Email - Request Rejected'),
        ('email_file_due', 'Email - File Due Reminder'),
        ('email_file_overdue', 'Email - File Overdue'),
        ('email_return_verified', 'Email - Return Verified'),
        ('email_return_rejected', 'Email - Return Rejected'),
        ('email_new_request', 'Email - New Request (Registry)'),
        ('email_weekly_summary', 'Email - Weekly Summary'),
        ('in_app_all', 'In-App - All Notifications'),
        ('in_app_important', 'In-App - Important Only'),
        ('in_app_none', 'In-App - No Notifications'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_prefs')
    
    # Email notifications
    email_request_approved = models.BooleanField(default=True)
    email_request_rejected = models.BooleanField(default=True)
    email_file_due = models.BooleanField(default=True)
    email_file_overdue = models.BooleanField(default=True)
    email_return_verified = models.BooleanField(default=True)
    email_return_rejected = models.BooleanField(default=True)
    email_new_request = models.BooleanField(default=True)
    email_weekly_summary = models.BooleanField(default=False)
    
    # In-app notifications
    in_app_notifications = models.CharField(
        max_length=20,
        choices=[
            ('all', 'All'),
            ('important', 'Important Only'),
            ('none', 'None'),
        ],
        default='all'
    )
    
    # Digest settings
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('never', 'Never'),
        ],
        default='weekly'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Preferences'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Notification preferences for {self.user.username}"


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
        ('pending_return', 'Pending Return Confirmation'),
        ('returned_verified', 'Returned & Verified'),
        ('return_rejected', 'Return Rejected'),
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
    
    # Return verification (for when user returns file)
    return_condition = models.CharField(
        max_length=20,
        choices=[
            ('good', 'Good Condition'),
            ('damaged', 'Damaged'),
            ('missing_pages', 'Missing Pages'),
            ('other', 'Other'),
        ],
        blank=True,
        null=True
    )
    return_notes = models.TextField(blank=True)
    return_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='return_verifications'
    )
    return_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Track the version that was approved/handed over (for post-return access)
    approved_version = models.ForeignKey(
        'FileVersion', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_requests',
        help_text='The file version that was approved and handed over to the user'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['requesting_user', 'status']),
            models.Index(fields=['file', 'status']),
            models.Index(fields=['status', 'processed_by']),
        ]
    
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
        
        # Capture the current file version as the approved version
        # This is the version the user will be able to access after returning
        current_version = self.file.versions.filter(file_attachment__isnull=False).order_by('-created_at').first()
        if current_version:
            self.approved_version = current_version
        
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
        
        # Check out the file to the user (file was held in registry until user confirmed receipt)
        self.file.check_out(
            user=self.requesting_user,
            department=self.requesting_department,
            notes=f'User confirmed receipt. Request ID: {self.pk}'
        )
        
        # Send email notification to user
        try:
            from register.emails import send_receipt_confirmation_notification
            send_receipt_confirmation_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
        
        # Send notification to registry
        if self.processed_by:
            Notification.objects.create(
                file=self.file,
                recipient=self.processed_by,
                sender=self.requesting_user,
                notification_type='user_confirmed',
                title=f'User Confirmed Receipt - {self.file.reference}',
                message=f'{self.requesting_user.get_full_name()} has confirmed receipt of file {self.file.reference}. File is now checked out to the user.'
            )
    
    def initiate_return(self, notes=''):
        """
        User initiates return of the file.
        This sends a notification to registry/admin to verify the return.
        """
        from django.contrib.auth.models import User
        
        self.status = 'pending_return'
        self.user_confirmation_notes = notes
        self.save()
        
        # Notify all registry and admin users
        registry_users = User.objects.filter(
            profile__role__in=['registry', 'admin']
        ) | User.objects.filter(is_superuser=True)
        
        for user in registry_users.distinct():
            Notification.objects.create(
                file=self.file,
                recipient=user,
                sender=self.requesting_user,
                notification_type='return_pending',
                title=f'File Return Pending Verification - {self.file.reference}',
                message=f'{self.requesting_user.get_full_name()} wants to return file {self.file.reference}. ' +
                        'Please verify the file condition and confirm the return.',
            )
        
        # Send email to registry
        try:
            from register.emails import send_return_pending_notification
            send_return_pending_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    def verify_return(self, verified_by, condition='good', notes=''):
        """
        Registry/Admin verifies the return of the file.
        This marks the file as returned and updates the file status.
        """
        from django.contrib.auth.models import User
        
        self.status = 'returned_verified'
        self.return_condition = condition
        self.return_notes = notes
        self.return_verified_by = verified_by
        self.return_verified_at = timezone.now()
        self.save()
        
        # Update the file status back to registry
        self.file.status = 'in_registry'
        self.file.current_holder = None
        self.file.save()
        
        # Log the activity
        from register.models import ActivityLog
        ActivityLog.objects.create(
            user=verified_by,
            action='file_return_verified',
            description=f'Returned and verified file: {self.file.reference}. Condition: {condition}',
        )
        
        # Notify the user who returned the file
        Notification.objects.create(
            file=self.file,
            recipient=self.requesting_user,
            sender=verified_by,
            notification_type='return_verified',
            title=f'File Return Verified - {self.file.reference}',
            message=f'Your return of file {self.file.reference} has been verified by registry. ' +
                    f'Condition: {condition.replace("_", " ").title()}. ' +
                    (f'Notes: {notes}' if notes else 'Thank you for returning the file.')
        )
        
        # Send email notification
        try:
            from register.emails import send_return_verified_notification
            send_return_verified_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    def reject_return(self, rejected_by, reason=''):
        """
        Registry/Admin rejects the return (e.g., file is damaged).
        """
        self.status = 'return_rejected'
        self.return_notes = reason
        self.return_verified_by = rejected_by
        self.return_verified_at = timezone.now()
        self.save()
        
        # Notify the user
        Notification.objects.create(
            file=self.file,
            recipient=self.requesting_user,
            sender=rejected_by,
            notification_type='return_rejected',
            title=f'File Return Rejected - {self.file.reference}',
            message=f'Your return of file {self.file.reference} has been rejected. ' +
                    f'Reason: {reason}. Please contact registry for more information.'
        )
        
        # Send email notification
        try:
            from register.emails import send_return_rejected_notification
            send_return_rejected_notification(self)
        except Exception as e:
            print(f"Email notification failed: {e}")

    def resubmit_return(self, notes=''):
        """
        User re-submits a return after their previous return was rejected.
        This puts the request back to 'pending_return' status so admin can verify the new document.
        """
        if self.status != 'return_rejected':
            return False
        
        self.status = 'pending_return'
        self.return_notes = notes
        self.return_verified_by = None
        self.return_verified_at = None
        self.save()
        
        # Notify registry
        from django.contrib.auth.models import User
        registry_users = User.objects.filter(
            profile__role__in=['registry', 'admin']
        ) | User.objects.filter(is_superuser=True)
        
        for user in registry_users.distinct():
            Notification.objects.create(
                file=self.file,
                recipient=user,
                sender=self.requesting_user,
                notification_type='return_resubmitted',
                title=f'File Return Re-submitted - {self.file.reference}',
                message=f'{self.requesting_user.get_full_name()} has re-submitted the return of file {self.file.reference}. ' +
                        'Please verify the new document.'
            )
        
        return True


class File(models.Model):
    LIFECYCLE_STATES = [
        ('available', 'Available'),
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('checked_out', 'Checked Out'),
        ('returned', 'Returned'),
        ('archived', 'Archived'),
    ]
    
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
    
    # Lifecycle state machine (formalized state)
    lifecycle_state = models.CharField(
        max_length=20, 
        choices=LIFECYCLE_STATES, 
        default='available',
        help_text="Formalized lifecycle state for transition validation"
    )
    lifecycle_transition_at = models.DateTimeField(null=True, blank=True, help_text="When the state last changed")
    lifecycle_transition_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='state_transitions', help_text="User who triggered the last state change"
    )
    
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
    
    # File attachment
    file_attachment = models.FileField(upload_to='files/%Y/%m/', blank=True, null=True, help_text="Main document file")
    original_filename = models.CharField(max_length=255, blank=True)
    
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
            models.Index(fields=['status', 'department']),
            models.Index(fields=['current_holder', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['year', 'department']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-generate sequence if not set
        if not self.sequence:
            last_file = File.objects.filter(
                department=self.department,
                year=self.year
            ).order_by('-sequence').first()
            self.sequence = (last_file.sequence + 1) if last_file else 1
        
        # Sync lifecycle_state with legacy status for existing records
        # This ensures backwards compatibility with existing data
        if self.pk and not self.lifecycle_state:
            state_map = {
                'in_registry': 'available',
                'checked_out': 'checked_out',
                'overdue': 'checked_out',
                'archived': 'archived',
            }
            self.lifecycle_state = state_map.get(self.status, 'available')
        
        # Ensure lifecycle_state is set for new objects
        if not self.lifecycle_state:
            self.lifecycle_state = 'available'
        
        super().save(*args, **kwargs)
        
        # Generate QR code if not exists
        if not self.qr_code:
            self.generate_qr_code()
    
    def generate_qr_code(self):
        """Generate QR code containing file reference with high error correction"""
        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=5,
            error_correction=qrcode.constants.ERROR_CORRECT_H  # High error correction
        )
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
        self.lifecycle_state = 'checked_out'
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
        self.lifecycle_state = 'available'
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
        
        if self.lifecycle_state == 'archived':
            return False, "File is already archived"
        
        self.status = 'archived'
        self.lifecycle_state = 'archived'
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
        if self.lifecycle_state != 'archived':
            return False, "File is not archived"
        
        self.status = 'in_registry'
        self.lifecycle_state = 'available'
        self.archived_at = None
        self.archived_by = None
        self.archive_reason = ''
        self.save()
        return True, "File restored successfully"
    
    def create_version(self, user, change_type='update', notes='', file_attachment=None, changes_summary=''):
        """Create a version snapshot of the file"""
        last_version = self.versions.first()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        version = FileVersion.objects.create(
            file=self,
            version_number=version_number,
            title=self.title,
            description=self.description,
            department=self.department,
            created_by=user,
            change_type=change_type,
            notes=notes,
            changes_summary=changes_summary,
            file_attachment=file_attachment,
            original_filename=getattr(file_attachment, 'name', '') if file_attachment else '',
            file_size=file_attachment.size if file_attachment else 0
        )
        return version
    
    def compare_versions(self, version1_id, version2_id):
        """Compare two versions and return differences"""
        from django.db.models import Model
        
        try:
            v1 = self.versions.get(id=version1_id)
            v2 = self.versions.get(id=version2_id)
        except FileVersion.DoesNotExist:
            return None, "Version not found"
        
        differences = []
        
        # Compare fields
        if v1.title != v2.title:
            differences.append(f"Title: '{v1.title}' → '{v2.title}'")
        if v1.description != v2.description:
            differences.append(f"Description changed")
        if v1.file_size != v2.file_size:
            diff_size = v2.file_size - v1.file_size
            differences.append(f"File size: {v1.file_size} bytes → {v2.file_size} bytes ({diff_size:+d})")
        if v1.original_filename != v2.original_filename:
            differences.append(f"Filename: '{v1.original_filename}' → '{v2.original_filename}'")
        
        # Check if file content changed
        file_changed = (v1.file_attachment != v2.file_attachment)
        if file_changed:
            differences.append("Document content: Modified")
        
        return differences, None
    
    def get_latest_version(self):
        """Get the most recent version"""
        return self.versions.first()
    
    def get_version_count(self):
        """Get total number of versions"""
        return self.versions.count()
    
    def can_transition_to(self, new_state):
        """Check if transition to new_state is valid"""
        from .state_machine import FileStateMachine
        return FileStateMachine.can_transition(self.lifecycle_state, new_state)
    
    def transition_to(self, new_state, user=None, notes=''):
        """Transition file to new state with validation"""
        from .state_machine import FileStateMachine, StateMachineError, transition_file_state
        
        if not self.can_transition_to(new_state):
            raise StateMachineError(
                f"Cannot transition from {FileStateMachine.get_display_name(self.lifecycle_state)} "
                f"to {FileStateMachine.get_display_name(new_state)}"
            )
        
        return transition_file_state(self, new_state, user, notes)
    
    @property
    def is_available(self):
        return self.lifecycle_state == 'available'
    
    @property
    def is_checked_out(self):
        return self.lifecycle_state == 'checked_out'
    
    @property
    def is_archived(self):
        return self.lifecycle_state == 'archived'
    
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
    
    # File attachment for this version
    file_attachment = models.FileField(upload_to='file_versions/%Y/%m/', blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    notes = models.TextField(blank=True)
    changes_summary = models.TextField(blank=True, help_text="Summary of changes from previous version")
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
    """Track user activities across the system - Immutable audit trail"""
    ACTION_TYPES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('password_reset', 'Password Reset'),
        ('profile_update', 'Profile Updated'),
        ('file_view', 'Viewed File'),
        ('file_download', 'Downloaded File'),
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
        ('comment_added', 'Added Comment'),
        ('file_return_verified', 'Return Verified'),
        ('file_return_rejected', 'Return Rejected'),
        ('file_state_change', 'File State Changed'),
        ('request_state_change', 'Request State Changed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities', null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False, help_text="Marked as archived for retention policy")
    
    # Tamper-resistant features
    entry_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash of this entry")
    previous_hash = models.CharField(max_length=64, blank=True, help_text="Hash of previous entry for chaining")
    checksum = models.CharField(max_length=64, blank=True, help_text="Checksum for integrity verification")
    
    # Digital signature for legally auditable approvals
    signature = models.TextField(blank=True, help_text="Digital signature for approvals")
    signature_algorithm = models.CharField(max_length=20, blank=True, help_text="Signature algorithm used")
    signed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, 
        related_name='signed_activities',
        help_text="User who digitally signed this entry"
    )
    signature_verified = models.BooleanField(
        default=False, 
        help_text="Whether signature has been verified"
    )
    
    # System info
    subsystem = models.CharField(max_length=50, default='main', help_text="System subsystem that generated this log")
    severity = models.CharField(
        max_length=20, 
        choices=[
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical'),
        ],
        default='info'
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['timestamp', 'subsystem']),
        ]
        # Prevent updates and deletes
        permissions = [
            ("view_audit_trail", "Can view audit trail"),
            ("export_audit_trail", "Can export audit trail"),
        ]
    
    def save(self, *args, **kwargs):
        # Generate hash before saving (but only for new objects)
        if not self.pk:
            self._generate_hash()
        super().save(*args, **kwargs)
    
    def _generate_hash(self):
        """Generate SHA-256 hash for this entry with chaining"""
        import hashlib
        import json
        
        # Get the previous hash from the last log entry
        if not self.previous_hash:
            last_log = ActivityLog.objects.order_by('-timestamp').first()
            self.previous_hash = last_log.entry_hash if last_log else 'genesis'
        
        # Create hash input
        hash_input = {
            'user_id': self.user.id if self.user else None,
            'user_username': self.user.username if self.user else 'system',
            'action': self.action,
            'description': self.description,
            'ip_address': self.ip_address,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat() if self.timestamp else timezone.now().isoformat(),
            'previous_hash': self.previous_hash,
            'subsystem': self.subsystem,
        }
        
        # Generate hash
        hash_string = json.dumps(hash_input, sort_keys=True)
        self.entry_hash = hashlib.sha256(hash_string.encode()).hexdigest()
        
        # Generate checksum (additional verification)
        checksum_input = f"{self.entry_hash}:{self.previous_hash}:{self.description}"
        self.checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:16]
    
    def verify_integrity(self):
        """Verify the integrity of this log entry"""
        import hashlib
        import json
        
        # Recreate the hash
        hash_input = {
            'user_id': self.user.id if self.user else None,
            'user_username': self.user.username if self.user else 'system',
            'action': self.action,
            'description': self.description,
            'ip_address': self.ip_address,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'previous_hash': self.previous_hash,
            'subsystem': self.subsystem,
        }
        
        hash_string = json.dumps(hash_input, sort_keys=True)
        computed_hash = hashlib.sha256(hash_string.encode()).hexdigest()
        
        return computed_hash == self.entry_hash
    
    def verify_chain(self):
        """Verify the entire chain up to this entry"""
        current = self
        while current.previous_hash and current.previous_hash != 'genesis':
            try:
                prev = ActivityLog.objects.get(entry_hash=current.previous_hash)
                if not prev.verify_integrity():
                    return False, f"Chain broken at {current.id}"
                current = prev
            except ActivityLog.DoesNotExist:
                return False, f"Previous hash {current.previous_hash} not found"
        return True, "Chain is valid"
    
    def sign_entry(self, user):
        """Digitally sign this audit entry for non-repudiation"""
        if not self.signature:
            # Create signature data
            sign_data = f"{self.action}:{self.description}:{self.timestamp.isoformat()}"
            self.signature_algorithm = 'SHA256-PSS'
            self.signed_by = user
            
            # Try to use digital signature if available
            try:
                sig = DigitalSignature.objects.get(user=user, is_active=True, is_revoked=False)
                self.signature = sig.sign(sign_data)
            except DigitalSignature.DoesNotExist:
                # Fallback: simple hash-based signature
                self.signature = hashlib.sha256(f"{sign_data}:{user.username}".encode()).hexdigest()
            
            self.signature_verified = True
    
    def verify_signature(self):
        """Verify the digital signature on this entry"""
        if not self.signature:
            return False, "No signature present"
        
        sign_data = f"{self.action}:{self.description}:{self.timestamp.isoformat()}"
        
        if self.signed_by:
            try:
                sig = DigitalSignature.objects.get(user=self.signed_by)
                if sig.verify(sign_data, self.signature):
                    return True, "Signature valid"
            except DigitalSignature.DoesNotExist:
                pass
        
        # Verify fallback signature
        expected = hashlib.sha256(f"{sign_data}:{self.signed_by.username}".encode()).hexdigest()
        if self.signature == expected:
            return True, "Signature valid (fallback)"
        
        return False, "Signature invalid"
    
    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.get_action_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_state = None
        self._skip_immutability = False  # For bulk operations
    
    def save_base(self, *args, **kwargs):
        """Override to prevent updates to existing records"""
        if self.pk and self._state.adding is False and not self._skip_immutability:
            from django.core.exceptions import ValidationError
            raise ValidationError("Cannot modify existing audit log entries")
        return super().save_base(*args, **kwargs)


class FileTag(models.Model):
    """Tags for organizing files"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color code
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class FileComment(models.Model):
    """Comments/notes on files for collaboration with nested replies"""
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='file_comments')
    content = models.TextField()
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='replies'
    )
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal comments are only visible to registry/admin"
    )
    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name_plural = 'File comments'
    
    def __str__(self):
        return f"Comment by {self.author} on {self.file.reference}"
    
    def get_replies(self):
        return self.replies.filter(is_internal=False).order_by('created_at')
    
    def get_all_replies(self):
        return self.replies.all().order_by('created_at')
    
    def is_reply(self):
        return self.parent is not None


class Webhook(models.Model):
    """Store webhook configurations for external systems"""
    
    EVENT_TYPES = [
        ('file_checkout', 'File Checked Out'),
        ('file_checkin', 'File Checked In'),
        ('file_upload', 'New File Uploaded'),
        ('request_approved', 'Request Approved'),
        ('request_rejected', 'Request Rejected'),
        ('request_completed', 'Request Completed'),
        ('file_returned', 'File Return Verified'),
    ]
    
    name = models.CharField(max_length=100, help_text="Webhook name for identification")
    url = models.URLField(help_text="External system URL to receive webhook")
    secret = models.CharField(max_length=128, blank=True, help_text="Secret key for signature verification")
    event_types = models.JSONField(default=list, help_text="List of events to trigger this webhook")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='webhooks')
    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, blank=True)
    failure_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.url}"


class WebhookDelivery(models.Model):
    """Track webhook delivery attempts"""
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=30)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event_type} - {self.status}"


class APIToken(models.Model):
    """API Token for external system authentication"""
    
    key = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    name = models.CharField(max_length=100, help_text="Name to identify this token")
    description = models.TextField(blank=True, help_text="Description of what this token is for")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    rate_limit = models.IntegerField(default=1000, help_text="Requests per hour")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        if not self.key:
            import secrets
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)


# Add tags field to File model
File.add_to_class('tags', models.ManyToManyField(
    FileTag, 
    blank=True, 
    related_name='files'
))


class LoginAttempt(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='login_attempts')
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    locked = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['username', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.username} - {self.status} - {self.timestamp}"


class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['-last_activity']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.ip_address} - {self.last_activity}"

    def duration(self):
        return self.last_activity - self.created_at


class AccessLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('file_view', 'File View'),
        ('file_download', 'File Download'),
        ('file_upload', 'File Upload'),
        ('file_checkout', 'File Checkout'),
        ('file_checkin', 'File Checkin'),
        ('file_request', 'File Request'),
        ('request_approve', 'Request Approve'),
        ('request_reject', 'Request Reject'),
        ('password_change', 'Password Change'),
        ('settings_change', 'Settings Change'),
        ('2fa_enable', '2FA Enable'),
        ('2fa_disable', '2FA Disable'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE, null=True, blank=True, related_name='security_access_logs')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"


class Task(models.Model):
    """Database-backed task queue for async processing"""
    
    TASK_TYPES = [
        ('email', 'Send Email'),
        ('webhook', 'Webhook Delivery'),
        ('cleanup', 'Cleanup Task'),
        ('notification', 'In-App Notification'),
        ('export', 'Export Task'),
    ]
    
    task_id = models.CharField(max_length=64, unique=True, db_index=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, db_index=True)
    task_name = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('retry', 'Retry'),
        ],
        default='pending',
        db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    last_error = models.TextField(blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    priority = models.PositiveIntegerField(default=10)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['priority', 'scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['task_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.task_type}: {self.task_name} ({self.status})"
