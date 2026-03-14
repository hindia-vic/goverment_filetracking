"""
Email notification utilities for File Tracking System
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model

User = get_user_model()


def send_file_request_notification(file_request):
    """Send email notification when a file checkout request is made"""
    subject = f'File Checkout Request - {file_request.file.reference}'
    
    # Get recipient (registry officers)
    recipients = User.objects.filter(
        profile__role__in=['registry', 'admin'],
        profile__is_active=True,
        is_active=True
    ).values_list('email', flat=True)
    
    if not recipients:
        return 0
    
    context = {
        'file_request': file_request,
        'file': file_request.file,
        'requester': file_request.requesting_user,
        'site_name': 'File Tracking System'
    }
    
    # Send to all registry officers
    sent_count = 0
    for recipient in recipients:
        if recipient:
            try:
                send_mail(
                    subject=subject,
                    message=f"""
Dear Registry Officer,

A new file checkout request has been submitted:

File: {file_request.file.reference} - {file_request.file.title}
Requested by: {file_request.requesting_user.get_full_name() or file_request.requesting_user.username}
Department: {file_request.requesting_department.name if file_request.requesting_department else 'N/A'}
Purpose: {file_request.purpose}

Please review and process this request.

Best regards,
File Tracking System
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                sent_count += 1
            except Exception as e:
                print(f"Error sending email: {e}")
    
    return sent_count


def send_request_approval_notification(file_request):
    """Send email when a request is approved"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'Request Approved - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

Your file checkout request has been APPROVED!

File: {file_request.file.reference} - {file_request.file.title}
Pickup Date: {file_request.pickup_date.strftime('%Y-%m-%d') if file_request.pickup_date else 'Please contact registry'}
Notes: {file_request.registry_notes or 'None'}

Please collect the file from the registry office.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
        return 1
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0


def send_request_rejection_notification(file_request):
    """Send email when a request is rejected"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'Request Rejected - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

Your file checkout request has been REJECTED.

File: {file_request.file.reference} - {file_request.file.title}
Reason: {file_request.registry_notes or 'No reason provided'}

Please contact the registry office for more information.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
        return 1
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0


def send_file_handover_notification(file_request):
    """Send email when file is handed over to user"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'File Ready for Pickup - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

Your file is ready for pickup!

File: {file_request.file.reference} - {file_request.file.title}
Handed by: {file_request.processed_by.get_full_name() if file_request.processed_by else 'Registry'}
Notes: {file_request.registry_notes or 'None'}

Please confirm your employee ID when collecting the file.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
        return 1
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0


def send_overdue_notification(file, holder):
    """Send email when a file becomes overdue"""
    if not holder.email:
        return 0
    
    subject = f'Overdue File Alert - {file.reference}'
    
    days_overdue = (file.due_date - file.checked_out_at).days if file.checked_out_at else 0
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {holder.get_full_name() or holder.username},

This is a reminder that the following file is OVERDUE:

File: {file.reference} - {file.title}
Due Date: {file.due_date.strftime('%Y-%m-%d') if file.due_date else 'N/A'}
Days Overdue: {abs(days_overdue)}

Please return this file to the registry as soon as possible.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[holder.email],
            fail_silently=False,
        )
        return 1
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0


def send_welcome_email(user):
    """Send welcome email to new users"""
    if not user.email:
        return 0
    
    subject = 'Welcome to File Tracking System'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {user.get_full_name() or user.username},

Welcome to the File Tracking System!

Your account has been created. Here are your login details:

Username: {user.username}
Email: {user.email}

Please log in and complete your profile with your employee ID and department.

If you have any questions, please contact the system administrator.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return 1
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0
