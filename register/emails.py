"""
Email notification utilities for File Tracking System
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import get_user_model

User = get_user_model()


def get_html_email_context(site_name="File Tracking System"):
    """Get common context for HTML emails"""
    return {
        'site_name': site_name,
        'base_url': getattr(settings, 'BASE_URL', 'http://localhost:8000'),
        'color_primary': '#0d6efd',
        'color_success': '#198754',
        'color_warning': '#ffc107',
        'color_danger': '#dc3545',
    }


def send_email_with_template(subject, content, recipient_list, context=None):
    """Send HTML email with template"""
    from .email_templates import EMAIL_TEMPLATE
    
    if context is None:
        context = get_html_email_context()
    
    # Render content into template
    context['content'] = content
    context['subject'] = subject
    
    # Simple template rendering
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f8f9fa; padding: 30px; border: 1px solid #e9ecef; border-radius: 0 0 10px 10px; }}
            .card {{ background: white; border-radius: 8px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .label {{ color: #6c757d; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
            .value {{ color: #212529; font-size: 16px; margin-bottom: 10px; }}
            .btn {{ display: inline-block; padding: 12px 24px; background: #0d6efd; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 10px 5px; }}
            .footer {{ text-align: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid #e9ecef; color: #6c757d; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📁 File Tracking System</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>This is an automated message from File Tracking System</p>
            <p>© 2026 File Tracking System. All rights reserved.</p>
        </div>
    </body>
    </html>
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=strip_tags(content),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_file_request_notification(file_request):
    """Send email notification when a file checkout request is made"""
    subject = f'📋 New File Request - {file_request.file.reference}'
    
    # Get recipient (registry officers)
    recipients = list(User.objects.filter(
        profile__role__in=['registry', 'admin'],
        profile__is_active=True,
        is_active=True
    ).values_list('email', flat=True))
    
    if not recipients:
        return 0
    
    content = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #0d6efd;">New File Request</h2>
    </div>
    
    <div class="card">
        <div class="label">File Reference</div>
        <div class="value" style="font-size: 20px; font-weight: bold;">{file_request.file.reference}</div>
        
        <div class="label">File Title</div>
        <div class="value">{file_request.file.title}</div>
        
        <div class="label">Requested By</div>
        <div class="value">{file_request.requesting_user.get_full_name() or file_request.requesting_user.username}</div>
        
        <div class="label">Department</div>
        <div class="value">{file_request.requesting_department.name if file_request.requesting_department else 'N/A'}</div>
        
        <div class="label">Purpose</div>
        <div class="value">{file_request.purpose}</div>
        
        <div class="label">Request Date</div>
        <div class="value">{file_request.created_at.strftime('%Y-%m-%d %H:%M')}</div>
    </div>
    
    <div style="text-align: center; margin-top: 20px;">
        <a href="{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/register/requests/?status=pending" class="btn">View Request</a>
    </div>
    """
    
    sent_count = 0
    for recipient in recipients:
        if recipient:
            if send_email_with_template(subject, content, [recipient]):
                sent_count += 1
    
    return sent_count


def send_request_approval_notification(file_request):
    """Send email when a request is approved"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'✅ Request Approved - {file_request.file.reference}'
    
    content = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #198754;">🎉 Request Approved!</h2>
    </div>
    
    <div class="card">
        <div class="label">File Reference</div>
        <div class="value" style="font-size: 20px; font-weight: bold; color: #198754;">{file_request.file.reference}</div>
        
        <div class="label">File Title</div>
        <div class="value">{file_request.file.title}</div>
        
        <div class="label">Pickup Date</div>
        <div class="value">{file_request.pickup_date.strftime('%Y-%m-%d') if file_request.pickup_date else 'Please contact registry'}</div>
        
        <div class="label">Notes from Registry</div>
        <div class="value">{file_request.registry_notes or 'None'}</div>
    </div>
    
    <p style="text-align: center; margin-top: 20px;">
        Please collect the file from the registry office during business hours.
    </p>
    
    <div style="text-align: center; margin-top: 20px;">
        <a href="{getattr(settings, 'BASE_URL', 'http://localhost:8000')}/register/files/{file_request.file.uuid}/" class="btn">View File Details</a>
    </div>
    """
    
    if send_email_with_template(subject, content, [recipient.email]):
        return 1
    return 0


def send_request_rejection_notification(file_request):
    """Send email when a request is rejected"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'❌ Request Rejected - {file_request.file.reference}'
    
    content = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #dc3545;">Request Rejected</h2>
    </div>
    
    <div class="card">
        <div class="label">File Reference</div>
        <div class="value" style="font-size: 20px; font-weight: bold; color: #dc3545;">{file_request.file.reference}</div>
        
        <div class="label">File Title</div>
        <div class="value">{file_request.file.title}</div>
        
        <div class="label">Reason</div>
        <div class="value">{file_request.registry_notes or 'No reason provided'}</div>
    </div>
    
    <p style="text-align: center; margin-top: 20px;">
        Please contact the registry office for more information.
    </p>
    """
    
    if send_email_with_template(subject, content, [recipient.email]):
        return 1
    return 0


def send_file_handover_notification(file_request):
    """Send email when file is handed over to user"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'📦 File Ready for Pickup - {file_request.file.reference}'
    
    content = f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #0d6efd;">File Ready for Pickup!</h2>
    </div>
    
    <div class="card">
        <div class="label">File Reference</div>
        <div class="value" style="font-size: 20px; font-weight: bold;">{file_request.file.reference}</div>
        
        <div class="label">File Title</div>
        <div class="value">{file_request.file.title}</div>
        
        <div class="label">Handed Over By</div>
        <div class="value">{file_request.processed_by.get_full_name() if file_request.processed_by else 'Registry'}</div>
        
        <div class="label">Handover Date</div>
        <div class="value">{file_request.handover_date.strftime('%Y-%m-%d %H:%M') if file_request.handover_date else 'N/A'}</div>
    </div>
    
    <p style="text-align: center; margin-top: 20px;">
        Please collect your file from the registry. Remember to return it by the due date!
    </p>
    """
    
    if send_email_with_template(subject, content, [recipient.email]):
        return 1
    return 0


def send_receipt_confirmation_notification(file_request):
    """Send email when user confirms receipt of file (file is now checked out)"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'File Checked Out - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

You have confirmed receipt of the file. The file has been checked out to you.

File: {file_request.file.reference} - {file_request.file.title}
Checked Out At: {file_request.file.checked_out_at.strftime('%Y-%m-%d %H:%M') if file_request.file.checked_out_at else 'N/A'}
Due Date: {file_request.file.due_date.strftime('%Y-%m-%d') if file_request.file.due_date else 'N/A'}

Please ensure you return the file by the due date.

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


def send_return_pending_notification(file_request):
    """Send email to registry when user wants to return a file"""
    from django.contrib.auth.models import User
    
    # Get all registry and admin users
    recipients = User.objects.filter(
        profiles__role__in=['registry', 'admin']
    ) | User.objects.filter(is_superuser=True)
    
    recipient_emails = [u.email for u in recipients.distinct() if u.email]
    
    if not recipient_emails:
        return 0
    
    subject = f'File Return Pending Verification - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear Registry/Admin,

A user wants to return a file and requires verification.

File: {file_request.file.reference} - {file_request.file.title}
Returned by: {file_request.requesting_user.get_full_name() or file_request.requesting_user.username}
Department: {file_request.requesting_user.profile.department.name if hasattr(file_request.requesting_user, 'profile') and file_request.requesting_user.profile.department else 'N/A'}

Please verify the file condition and confirm the return in the system.

Best regards,
File Tracking System
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_emails,
            fail_silently=False,
        )
        return len(recipient_emails)
    except Exception as e:
        print(f"Error sending email: {e}")
        return 0


def send_return_verified_notification(file_request):
    """Send email to user when their return is verified"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    condition_display = {
        'good': 'Good Condition',
        'damaged': 'Damaged',
        'missing_pages': 'Missing Pages',
        'other': 'Other'
    }.get(file_request.return_condition, file_request.return_condition)
    
    subject = f'File Return Verified - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

Your file return has been verified by the registry.

File: {file_request.file.reference} - {file_request.file.title}
Condition: {condition_display}
{f"Notes: {file_request.return_notes}" if file_request.return_notes else ""}

The file has been returned to the registry.

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


def send_return_rejected_notification(file_request):
    """Send email to user when their file return is rejected"""
    recipient = file_request.requesting_user
    
    if not recipient.email:
        return 0
    
    subject = f'File Return Rejected - {file_request.file.reference}'
    
    try:
        send_mail(
            subject=subject,
            message=f"""
Dear {recipient.get_full_name() or recipient.username},

Your file return has been rejected by the registry.

File: {file_request.file.reference} - {file_request.file.title}
Reason: {file_request.return_notes or 'No reason provided'}

Please contact the registry for more information to resolve this issue.

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
