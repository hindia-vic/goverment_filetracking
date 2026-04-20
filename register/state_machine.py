"""
File Lifecycle State Machine

Formal state transitions following: AVAILABLE → REQUESTED → APPROVED → CHECKED_OUT → RETURNED → ARCHIVED
"""

from django.core.exceptions import ValidationError
from django.utils import timezone


class StateMachineError(Exception):
    """Custom exception for state machine violations"""
    pass


class FileStateMachine:
    """
    File lifecycle state machine with strict transition validation.
    
    States:
    - available: File is in registry and available for request
    - requested: File has been requested by a user (pending approval)
    - approved: Request has been approved, file ready for pickup
    - checked_out: File has been handed over to the requester
    - returned: File has been returned to registry
    - archived: File has been archived
    
    Transitions:
    - available → requested (when user creates a request)
    - requested → approved (when registry approves the request)
    - approved → checked_out (when user confirms receipt)
    - checked_out → returned (when user returns the file)
    - returned → available (when registry verifies the return)
    - available → archived (when file is archived)
    - archived → available (when file is restored)
    """
    
    STATES = ['available', 'requested', 'approved', 'checked_out', 'returned', 'archived']
    
    # Define valid transitions: from_state -> [allowed_to_states]
    TRANSITIONS = {
        'available': ['requested', 'archived'],
        'requested': ['approved', 'cancelled'],
        'approved': ['checked_out', 'cancelled'],
        'checked_out': ['returned'],
        'returned': ['available', 'archived'],
        'archived': ['available'],
    }
    
    # Legacy state mapping (for compatibility with existing data)
    LEGACY_MAP = {
        'in_registry': 'available',
        'checked_out': 'checked_out',
        'overdue': 'checked_out',  # Overdue is a sub-state of checked_out
        'archived': 'archived',
    }
    
    @classmethod
    def get_display_name(cls, state):
        """Get human-readable display name for state"""
        names = {
            'available': 'Available',
            'requested': 'Requested',
            'approved': 'Approved',
            'checked_out': 'Checked Out',
            'returned': 'Returned',
            'archived': 'Archived',
        }
        return names.get(state, state.title())
    
    @classmethod
    def can_transition(cls, from_state, to_state):
        """Check if transition is valid"""
        allowed = cls.TRANSITIONS.get(from_state, [])
        return to_state in allowed
    
    @classmethod
    def validate_transition(cls, from_state, to_state):
        """Validate transition and raise error if invalid"""
        if not cls.can_transition(from_state, to_state):
            raise StateMachineError(
                f"Invalid transition: Cannot transition from '{cls.get_display_name(from_state)}' "
                f"to '{cls.get_display_name(to_state)}'"
            )
        return True
    
    @classmethod
    def get_allowed_transitions(cls, current_state):
        """Get list of states that can be transitioned to from current state"""
        return cls.TRANSITIONS.get(current_state, [])


class RequestStateMachine:
    """
    Request lifecycle state machine.
    
    States:
    - pending: Request submitted, waiting for approval
    - approved: Request approved by registry
    - rejected: Request rejected by registry
    - ready: File ready for pickup
    - handed_over: File handed to user
    - confirmed: User confirmed receipt
    - pending_return: User initiated return
    - returned: Return verified by registry
    - return_rejected: Return rejected (file damaged etc)
    - cancelled: Request cancelled
    
    Transitions:
    - pending → approved/rejected/cancelled
    - approved → ready/cancelled
    - ready → handed_over
    - handed_over → confirmed
    - confirmed → pending_return
    - pending_return → returned/return_rejected
    - returned → (terminal state)
    - return_rejected → pending_return (resubmit)
    """
    
    STATES = ['pending', 'approved', 'rejected', 'ready', 'handed_over', 
              'confirmed', 'pending_return', 'returned', 'return_rejected', 'cancelled']
    
    TRANSITIONS = {
        'pending': ['approved', 'rejected', 'cancelled'],
        'approved': ['ready', 'cancelled'],
        'ready': ['handed_over'],
        'handed_over': ['confirmed'],
        'confirmed': ['pending_return'],
        'pending_return': ['returned', 'return_rejected'],
        'return_rejected': ['pending_return'],  # Allow resubmit
        'rejected': [],  # Terminal
        'returned': [],  # Terminal
        'cancelled': [],  # Terminal
    }
    
    @classmethod
    def get_display_name(cls, state):
        names = {
            'pending': 'Pending',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'ready': 'Ready for Pickup',
            'handed_over': 'Handed Over',
            'confirmed': 'Confirmed',
            'pending_return': 'Pending Return',
            'returned': 'Returned',
            'return_rejected': 'Return Rejected',
            'cancelled': 'Cancelled',
        }
        return names.get(state, state.title())
    
    @classmethod
    def can_transition(cls, from_state, to_state):
        allowed = cls.TRANSITIONS.get(from_state, [])
        return to_state in allowed
    
    @classmethod
    def validate_transition(cls, from_state, to_state):
        if not cls.can_transition(from_state, to_state):
            raise StateMachineError(
                f"Invalid transition: Cannot transition from '{cls.get_display_name(from_state)}' "
                f"to '{cls.get_display_name(to_state)}'"
            )
        return True


def transition_file_state(file, new_state, user=None, notes=''):
    """
    Transition a file to a new state with validation and logging.
    
    Args:
        file: File instance
        new_state: Target state string
        user: User performing the transition
        notes: Optional notes about the transition
    
    Returns:
        True if transition successful
    
    Raises:
        StateMachineError if transition is invalid
    """
    old_state = file.lifecycle_state
    
    # Validate transition
    FileStateMachine.validate_transition(old_state, new_state)
    
    # Perform transition
    file.lifecycle_state = new_state
    file.lifecycle_transition_at = timezone.now()
    
    if user:
        file.lifecycle_transition_by = user
    
    # Update legacy status field for compatibility
    legacy_map = {
        'available': 'in_registry',
        'checked_out': 'checked_out',
        'returned': 'in_registry',
        'archived': 'archived',
    }
    file.status = legacy_map.get(new_state, file.status)
    
    file.save()
    
    # Log the transition
    from .models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        action='file_state_change',
        description=f"File {file.reference} transitioned from {FileStateMachine.get_display_name(old_state)} to {FileStateMachine.get_display_name(new_state)}",
        metadata={'old_state': old_state, 'new_state': new_state, 'notes': notes}
    )
    
    return True


def transition_request_state(request, new_state, user=None, notes=''):
    """
    Transition a request to a new state with validation and logging.
    """
    old_state = request.status
    
    RequestStateMachine.validate_transition(old_state, new_state)
    
    request.status = new_state
    request.updated_at = timezone.now()
    request.save()
    
    from .models import ActivityLog
    ActivityLog.objects.create(
        user=user,
        action='request_state_change',
        description=f"Request #{request.id} transitioned from {RequestStateMachine.get_display_name(old_state)} to {RequestStateMachine.get_display_name(new_state)}",
        metadata={'old_state': old_state, 'new_state': new_state, 'notes': notes}
    )
    
    return True