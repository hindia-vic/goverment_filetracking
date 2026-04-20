"""
Concurrency Control for File Tracking System

Handles race conditions and concurrent access issues using:
1. Database-level locking (SELECT FOR UPDATE)
2. Optimistic locking with version fields
3. Atomic operations
"""

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging
from register.models import File, FileRequest

_logger = logging.getLogger(__name__)


class ConcurrentModificationError(Exception):
    """Raised when a concurrent modification is detected"""
    pass


class FileLockManager:
    """
    Manages database-level locking for file operations.
    Uses SELECT FOR UPDATE to prevent race conditions.
    """
    
    @staticmethod
    def lock_file_for_update(file_id):
        """
        Lock a file row for update to prevent concurrent modifications.
        
        Usage:
            with lock_file_for_update(file_id):
                # perform operations
                pass
        """
        from register.models import File
        return File.objects.select_for_update().filter(id=file_id)
    
    @staticmethod
    def lock_file_version_for_update(file_id):
        """
        Lock file versions for update.
        """
        from register.models import FileVersion
        return FileVersion.objects.select_for_update().filter(file_id=file_id)
    
    @staticmethod
    def get_file_with_lock(uuid):
        """Get file with lock for update"""
        from register.models import File
        return File.objects.select_for_update().get(uuid=uuid)


class OptimisticLockMixin:
    """
    Mixin for optimistic locking using version field.
    Requires model to have a 'version' field.
    """
    
    @classmethod
    def get_with_optimistic_lock(cls, pk, expected_version):
        """
        Get object only if version matches (optimistic locking).
        
        Args:
            pk: Primary key of the object
            expected_version: Expected version for concurrency control
            
        Returns:
            The object if version matches
            
        Raises:
            ConcurrentModificationError: If version doesn't match
        """
        try:
            obj = cls.objects.get(pk=pk)
            if hasattr(obj, 'version') and obj.version != expected_version:
                raise ConcurrentModificationError(
                    f"Object {cls.__name__} with pk={pk} was modified by another user. "
                    f"Expected version {expected_version}, found {obj.version}. "
                    "Please refresh and try again."
                )
            return obj
        except cls.DoesNotExist:
            raise ValidationError(f"{cls.__name__} with pk={pk} not found")
    
    def save_with_optimistic_lock(self, expected_version=None, **kwargs):
        """
        Save object with optimistic locking.
        
        Args:
            expected_version: Expected version for concurrency check
            
        Raises:
            ConcurrentModificationError: If version doesn't match
        """
        if expected_version is not None and hasattr(self, 'version'):
            if self.version != expected_version:
                raise ConcurrentModificationError(
                    f"Object was modified by another user. "
                    f"Expected version {expected_version}, current version {self.version}. "
                    "Please refresh and try again."
                )
        
        if hasattr(self, 'version'):
            self.version += 1
            
        return self.save(**kwargs)


def safe_file_request(file, user, purpose):
    """
    Safely create a file request with concurrency control.
    
    Uses database-level locking to prevent duplicate requests.
    
    Args:
        file: File instance
        user: User making the request
        purpose: Purpose of the request
        
    Returns:
        FileRequest instance if successful
        
    Raises:
        ValidationError: If file is not available or request already exists
        ConcurrentModificationError: If concurrent modification detected
    """
    from register.models import FileRequest
    from django.db import connection
    
    with transaction.atomic():
        # Lock the file row to prevent concurrent modifications
        file_locked = File.objects.select_for_update().filter(
            id=file.id,
            lifecycle_state='available'
        ).first()
        
        if not file_locked:
            raise ValidationError(
                f"File {file.reference} is not available for request. "
                f"Current state: {file.get_lifecycle_state_display()}"
            )
        
        # Check for existing pending requests (within the transaction)
        existing_request = FileRequest.objects.filter(
            file=file,
            requesting_user=user,
            status__in=['pending', 'approved', 'ready_for_pickup']
        ).select_for_update().first()
        
        if existing_request:
            raise ValidationError(
                f"You already have a {existing_request.get_status_display()} request for this file"
            )
        
        # Create the request
        file_request = FileRequest.objects.create(
            file=file,
            requesting_user=user,
            requesting_department=user.profile.department if hasattr(user, 'profile') and user.profile else None,
            purpose=purpose,
            status='pending'
        )
        
        # Update file state to requested
        file_locked.lifecycle_state = 'requested'
        file_locked.save(update_fields=['lifecycle_state', 'updated_at'])
        
        return file_request


def safe_request_approve(request_obj, processed_by, pickup_date=None, notes=''):
    """
    Safely approve a file request with concurrency control.
    
    Args:
        request_obj: FileRequest instance
        processed_by: User approving the request
        pickup_date: Optional pickup date
        notes: Optional notes
        
    Returns:
        Updated FileRequest instance
        
    Raises:
        ValidationError: If request cannot be approved
        ConcurrentModificationError: If concurrent modification detected
    """
    from register.models import File
    
    with transaction.atomic():
        # Lock the request
        request_locked = FileRequest.objects.select_for_update().get(
            id=request_obj.id
        )
        
        # Validate current state
        if request_locked.status != 'pending':
            raise ValidationError(
                f"Request cannot be approved. Current status: {request_locked.get_status_display()}"
            )
        
        # Lock the file
        file_locked = File.objects.select_for_update().get(
            id=request_locked.file_id
        )
        
        # Check file is in valid state
        if file_locked.lifecycle_state != 'requested':
            raise ValidationError(
                f"File is not in requested state. Current state: {file_locked.get_lifecycle_state_display()}"
            )
        
        # Update request status
        request_locked.status = 'ready_for_pickup'
        request_locked.processed_by = processed_by
        request_locked.processed_at = timezone.now()
        request_locked.pickup_date = pickup_date
        request_locked.registry_notes = notes
        request_locked.save()
        
        # Update file state to approved
        file_locked.lifecycle_state = 'approved'
        file_locked.save(update_fields=['lifecycle_state', 'updated_at'])
        
        return request_locked


def safe_request_reject(request_obj, processed_by, reason=''):
    """
    Safely reject a file request with concurrency control.
    """
    from register.models import File
    
    with transaction.atomic():
        request_locked = FileRequest.objects.select_for_update().get(
            id=request_obj.id
        )
        
        if request_locked.status != 'pending':
            raise ValidationError(
                f"Request cannot be rejected. Current status: {request_locked.get_status_display()}"
            )
        
        # Update request status
        request_locked.status = 'rejected'
        request_locked.processed_by = processed_by
        request_locked.processed_at = timezone.now()
        request_locked.registry_notes = reason
        request_locked.save()
        
        # Release file back to available
        file_locked = File.objects.select_for_update().get(
            id=request_locked.file_id
        )
        if file_locked.lifecycle_state == 'requested':
            file_locked.lifecycle_state = 'available'
            file_locked.save(update_fields=['lifecycle_state', 'updated_at'])
        
        return request_locked


def safe_file_handover(request_obj, processed_by, notes=''):
    """
    Safely hand over a file to the requester with concurrency control.
    """
    from register.models import File
    
    with transaction.atomic():
        request_locked = FileRequest.objects.select_for_update().get(
            id=request_obj.id
        )
        
        if request_locked.status != 'ready_for_pickup':
            raise ValidationError(
                f"File cannot be handed over. Current status: {request_locked.get_status_display()}"
            )
        
        file_locked = File.objects.select_for_update().get(
            id=request_locked.file_id
        )
        
        # Hand over the file
        file_locked.check_out(
            user=request_locked.requesting_user,
            department=request_locked.requesting_department,
            notes=notes
        )
        
        # Update file state to checked_out
        file_locked.lifecycle_state = 'checked_out'
        file_locked.save(update_fields=['lifecycle_state', 'updated_at'])
        
        # Update request status
        request_locked.status = 'handed_over'
        request_locked.processed_by = processed_by
        request_locked.processed_at = timezone.now()
        request_locked.registry_notes = notes
        request_locked.save()
        
        # Capture current version as approved version
        current_version = file_locked.versions.filter(
            file_attachment__isnull=False
        ).order_by('-created_at').first()
        
        if current_version:
            request_locked.approved_version = current_version
            request_locked.save(update_fields=['approved_version'])
        
        return request_locked


def safe_file_return(request_obj, verified_by, condition='good', notes=''):
    """
    Safely verify file return with concurrency control.
    """
    from register.models import File
    
    with transaction.atomic():
        request_locked = FileRequest.objects.select_for_update().get(
            id=request_obj.id
        )
        
        if request_locked.status != 'pending_return':
            raise ValidationError(
                f"File return cannot be verified. Current status: {request_locked.get_status_display()}"
            )
        
        file_locked = File.objects.select_for_update().get(
            id=request_locked.file_id
        )
        
        # Verify return
        request_locked.status = 'returned_verified'
        request_locked.return_condition = condition
        request_locked.return_notes = notes
        request_locked.return_verified_by = verified_by
        request_locked.return_verified_at = timezone.now()
        request_locked.save()
        
        # Return file to registry
        file_locked.check_in(user=verified_by, notes=notes)
        
        # Update file state to available
        file_locked.lifecycle_state = 'available'
        file_locked.save(update_fields=['lifecycle_state', 'updated_at'])
        
        return request_locked


def bulk_operation_atomic(items, operation_func, *args, **kwargs):
    """
    Perform atomic bulk operations on files.
    
    Args:
        items: List of item IDs to process
        operation_func: Function to call for each item
        *args, **kwargs: Additional arguments for operation_func
        
    Returns:
        List of results (successful and failed)
    """
    from register.models import File
    
    results = {
        'successful': [],
        'failed': []
    }
    
    with transaction.atomic():
        for item_id in items:
            try:
                # Lock each file individually
                file_obj = File.objects.select_for_update().get(id=item_id)
                result = operation_func(file_obj, *args, **kwargs)
                results['successful'].append({
                    'id': item_id,
                    'result': result
                })
            except Exception as e:
                results['failed'].append({
                    'id': item_id,
                    'error': str(e)
                })
                _logger.error(f"Bulk operation failed for file {item_id}: {e}")
    
    return results