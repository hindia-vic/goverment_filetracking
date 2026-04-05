import io
import logging
import os
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import login
from django.contrib.auth.backends import ModelBackend
from django.views.generic import ListView, DetailView, CreateView, View, UpdateView, DeleteView
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, FileResponse, JsonResponse
from django.db.models import Q, Count
from django.http import HttpResponseNotFound
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse_lazy, reverse
from django.contrib.messages.views import SuccessMessageMixin
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .models import File, FileMovement, Department, UserProfile, Notification, FileRequest, ActivityLog, FileVersion, FileTag, FileComment
from django.contrib.auth.models import User
from .forms import (
    FileUploadForm, CheckoutForm, CheckinForm, AuditFilterForm,
    UserRegistrationForm, UserProfileForm, DepartmentForm,
    FileRequestForm, FileRequestApprovalForm, FileHandoverForm, UserConfirmationForm,
    FileTagForm
)
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)


@method_decorator(ratelimit(key='ip', rate='5/h', method='POST', block=True), name='post')
class RegisterView(View):
    """User self-registration view"""
    template_name = 'register/register.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = UserRegistrationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Set the backend attribute before login when using multiple authentication backends
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to File Tracking System.')
            
            # Send welcome email
            try:
                from register.emails import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                print(f"Welcome email failed: {e}")
            
            return redirect('dashboard')
        return render(request, self.template_name, {'form': form})


class DepartmentListView(LoginRequiredMixin, ListView):
    """List all departments (admin only)"""
    model = Department
    template_name = 'register/department_list.html'
    context_object_name = 'departments'
    
    def get_queryset(self):
        if not (self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.role in ['admin'])):
            from django.http import Http403Forbidden
            raise Http403Forbidden("You don't have permission to view this page.")
        return Department.objects.all()


class DepartmentCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Create new department (admin only)"""
    model = Department
    form_class = DepartmentForm
    template_name = 'register/department_form.html'
    success_url = reverse_lazy('department_list')
    success_message = 'Department created successfully'
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['admin'])):
            messages.error(request, "You don't have permission to create departments.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class DepartmentUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Update department (admin only)"""
    model = Department
    form_class = DepartmentForm
    template_name = 'register/department_form.html'
    success_url = reverse_lazy('department_list')
    success_message = 'Department updated successfully'
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['admin'])):
            messages.error(request, "You don't have permission to edit departments.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class UserListView(LoginRequiredMixin, ListView):
    """List all users (admin only)"""
    model = UserProfile
    template_name = 'register/user_list.html'
    context_object_name = 'profiles'
    
    def get_queryset(self):
        if not (self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.role in ['admin'])):
            messages.error(self.request, "You don't have permission to view this page.")
            return UserProfile.objects.none()
        return UserProfile.objects.select_related('user', 'department').all()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Update user profile (admin only)"""
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'register/user_form.html'
    success_url = reverse_lazy('user_list')
    success_message = 'User profile updated successfully'
    
    def get_object(self):
        return get_object_or_404(UserProfile, pk=self.kwargs['pk'])
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['admin_user'] = self.request.user
        return kwargs
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['admin'])):
            messages.error(request, "You don't have permission to edit users.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class NotificationListView(LoginRequiredMixin, ListView):
    """List user's notifications"""
    model = Notification
    template_name = 'register/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('file', 'sender')


class NotificationDetailView(LoginRequiredMixin, View):
    """View and mark notification as read"""
    
    def get(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.mark_as_read()
        
        # Redirect to related file
        return redirect('file_detail', uuid=notification.file.uuid)


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    """Mark all notifications as read"""
    
    def post(self, request):
        Notification.objects.filter(
            recipient=request.user,
            status='pending'
        ).update(status='read')
        
        messages.success(request, 'All notifications marked as read.')
        return redirect('notification_list')


class NotificationClearView(LoginRequiredMixin, View):
    """Delete a single notification"""
    
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.delete()
        
        messages.success(request, 'Notification deleted.')
        return redirect('notification_list')


class NotificationClearAllView(LoginRequiredMixin, View):
    """Delete all notifications for the user"""
    
    def post(self, request):
        Notification.objects.filter(recipient=request.user).delete()
        
        messages.success(request, 'All notifications cleared.')
        return redirect('notification_list')


class FileRequestCreateView(LoginRequiredMixin, View):
    """User requests to checkout a file"""
    template_name = 'register/file_request.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        # Check if file is available
        if file.status != 'in_registry':
            messages.error(request, f'File is currently {file.get_status_display()}. Cannot request.')
            return redirect('file_detail', uuid=uuid)
        
        # Check if user already has pending request
        existing_request = FileRequest.objects.filter(
            file=file,
            requesting_user=request.user,
            status__in=['pending', 'approved', 'ready_for_pickup']
        ).first()
        
        if existing_request:
            messages.warning(request, 'You already have a pending request for this file.')
            return redirect('file_detail', uuid=uuid)
        
        form = FileRequestForm()
        return render(request, self.template_name, {'file': file, 'form': form})
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        form = FileRequestForm(request.POST)
        
        # Check if user's profile is active
        user_is_active = True
        try:
            if hasattr(request.user, 'profile') and request.user.profile:
                user_is_active = request.user.profile.is_active
            else:
                # Check UserProfile model directly
                profile = UserProfile.objects.get(user=request.user)
                user_is_active = profile.is_active
        except UserProfile.DoesNotExist:
            user_is_active = False
        except Exception:
            user_is_active = True
        
        if not user_is_active:
            messages.error(request, 'Your account is inactive. You cannot request files. Please contact the administrator.')
            return redirect('file_detail', uuid=uuid)
        
        if form.is_valid():
            # Create the file request
            file_request = FileRequest.objects.create(
                file=file,
                requesting_user=request.user,
                requesting_department=request.user.profile.department if hasattr(request.user, 'profile') else None,
                purpose=form.cleaned_data['purpose'],
                status='pending'
            )
            
            # Send notification to all registry officers
            registry_profiles = UserProfile.objects.filter(role='registry', is_active=True)
            for profile in registry_profiles:
                Notification.objects.create(
                    file=file,
                    recipient=profile.user,
                    sender=request.user,
                    notification_type='checkout_request',
                    title=f'Checkout Request - {file.reference}',
                    message=f'{request.user.get_full_name()} has requested file {file.reference}. Purpose: {form.cleaned_data["purpose"]}'
                )
            
            messages.success(request, 'Your request has been submitted. You will be notified when ready for pickup.')
            return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {'file': file, 'form': form})


class FileRequestListView(LoginRequiredMixin, View):
    """List all file requests (for registry and admin)"""
    template_name = 'register/request_list.html'
    
    def get(self, request):
        # Only registry and admin can view all requests
        user_is_admin_or_registry = False
        if request.user.is_superuser:
            user_is_admin_or_registry = True
        elif hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin']:
            user_is_admin_or_registry = True
            
        # Handle CSV export
        if request.GET.get('export') == 'csv':
            from .export_utils import export_requests_to_csv
            if user_is_admin_or_registry:
                status_filter = request.GET.get('status', 'pending')
                requests = FileRequest.objects.filter(
                    status=status_filter
                ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            else:
                requests = FileRequest.objects.filter(
                    requesting_user=request.user
                ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            return export_requests_to_csv(requests)
        
        if not user_is_admin_or_registry:
            # Department users only see their own requests
            requests = FileRequest.objects.filter(
                requesting_user=request.user
            ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            pending_count = 0
            return_count = 0
        else:
            # Registry and admin see all pending requests
            status_filter = request.GET.get('status', 'pending')
            
            # Allow filtering by pending_return status too
            if status_filter == 'pending_return':
                requests = FileRequest.objects.filter(
                    status='pending_return'
                ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            else:
                requests = FileRequest.objects.filter(
                    status=status_filter
                ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            
            pending_count = FileRequest.objects.filter(status='pending').count()
            return_count = FileRequest.objects.filter(status='pending_return').count()
        
        return render(request, self.template_name, {
            'requests': requests,
            'current_status': request.GET.get('status', 'pending'),
            'pending_count': pending_count,
            'return_count': return_count if 'return_count' in locals() else 0
        })


class FileRequestProcessView(LoginRequiredMixin, View):
    """Process file request (approve/reject) - Registry only"""
    template_name = 'register/request_process.html'
    
    def get(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request has already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to process requests.')
            return redirect('request_list')
        
        form = FileRequestApprovalForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request has already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        form = FileRequestApprovalForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data.get('notes', '')
            pickup_date = form.cleaned_data.get('pickup_date')
            
            if action == 'approve':
                file_request.approve(
                    processed_by=request.user,
                    pickup_date=pickup_date,
                    notes=notes
                )
                messages.success(request, f'Request approved. User has been notified.')
            else:
                file_request.reject(
                    processed_by=request.user,
                    reason=notes
                )
                messages.success(request, 'Request rejected. User has been notified.')
            
            return redirect('request_list')
        
        return render(request, self.template_name, {'file_request': file_request, 'form': form})


class FileRequestHandoverView(LoginRequiredMixin, View):
    """Confirm file has been handed to user - Registry only"""
    template_name = 'register/request_handover.html'
    
    def get(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, status='ready_for_pickup')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be processed for handover. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to handover files.')
            return redirect('request_list')
        
        form = FileHandoverForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, status='ready_for_pickup')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be processed for handover. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        form = FileHandoverForm(request.POST)
        
        if form.is_valid():
            # Verify confirmation code matches requesting user's employee ID
            expected_code = file_request.requesting_user.profile.employee_id if hasattr(file_request.requesting_user, 'profile') else ''
            
            if form.cleaned_data['confirmation_code'] != expected_code:
                messages.error(request, 'Invalid confirmation code.')
                return render(request, self.template_name, {'file_request': file_request, 'form': form})
            
            # Mark as handed over - file stays in registry until user confirms receipt
            file_request.mark_handed_over(
                processed_by=request.user,
                notes=form.cleaned_data.get('notes', '')
            )
            
            messages.success(request, 'File handed over successfully. User has been notified to confirm receipt.')
            return redirect('request_list')
        
        return render(request, self.template_name, {'file_request': file_request, 'form': form})


class FileRequestConfirmView(LoginRequiredMixin, View):
    """User confirms receipt of file"""
    template_name = 'register/request_confirm.html'
    
    def get(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, requesting_user=request.user, status='handed_over')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk, requesting_user=request.user).exists():
                messages.error(request, 'This request cannot be confirmed. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('dashboard')
        
        form = UserConfirmationForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        try:
            file_request = FileRequest.objects.get(pk=pk, requesting_user=request.user, status='handed_over')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk, requesting_user=request.user).exists():
                messages.error(request, 'This request cannot be confirmed. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('dashboard')
        
        form = UserConfirmationForm(request.POST)
        
        if form.is_valid():
            # Verify confirmation code
            expected_code = request.user.profile.employee_id if hasattr(request.user, 'profile') else ''
            
            if form.cleaned_data['confirmation_code'] != expected_code:
                messages.error(request, 'Invalid confirmation code.')
                return render(request, self.template_name, {'file_request': file_request, 'form': form})
            
            file_request.confirm_receipt(notes=form.cleaned_data.get('notes', ''))
            
            messages.success(request, 'Thank you for confirming! Your confirmation has been recorded.')
            return redirect('file_detail', uuid=file_request.file.uuid)
        
        return render(request, self.template_name, {'file_request': file_request, 'form': form})


class FileReturnInitiateView(LoginRequiredMixin, View):
    """User initiates return of a file - notifies registry to verify"""
    template_name = 'register/request_return.html'
    
    def get(self, request, pk):
        file_request = get_object_or_404(
            FileRequest, 
            pk=pk, 
            requesting_user=request.user, 
            status__in=['handed_over', 'confirmed']
        )
        
        # Check if file has an attachment - if so, user must upload during return
        file = file_request.file
        has_attachment = file.file_attachment or file.versions.filter(file_attachment__isnull=False).exists()
        
        return render(request, self.template_name, {
            'file_request': file_request,
            'has_attachment': has_attachment
        })
    
    def post(self, request, pk):
        file_request = get_object_or_404(
            FileRequest, 
            pk=pk, 
            requesting_user=request.user, 
            status__in=['handed_over', 'confirmed']
        )
        
        file = file_request.file
        
        # Check if file has an attachment - if so, user must upload during return
        has_attachment = file.file_attachment or file.versions.filter(file_attachment__isnull=False).exists()
        
        notes = request.POST.get('notes', '')
        uploaded_file = request.FILES.get('file_attachment')
        
        # If file has attachment, require upload
        if has_attachment and not uploaded_file:
            messages.error(request, 'This file has a document attachment. You must upload the document when returning the file.')
            return render(request, self.template_name, {
                'file_request': file_request,
                'has_attachment': has_attachment
            })
        
        # If file is uploaded, create a new version
        if uploaded_file:
            # Create new version with the uploaded file
            version = file.create_version(
                user=request.user,
                change_type='return',
                notes=notes,
                file_attachment=uploaded_file
            )
            # Update the main file attachment
            file.file_attachment = uploaded_file
            file.original_filename = uploaded_file.name
            file.save()
        
        # Initiate return - this will notify registry
        file_request.initiate_return(notes=notes)
        
        messages.success(
            request, 
            'Your return request has been submitted. Registry will verify the file condition and confirm the return.'
        )
        return redirect('file_detail', uuid=file.uuid)


class FileReturnResubmitView(LoginRequiredMixin, View):
    """User resubmits a return after their previous return was rejected"""
    template_name = 'register/request_return_resubmit.html'
    
    def get(self, request, pk):
        file_request = get_object_or_404(
            FileRequest, 
            pk=pk, 
            requesting_user=request.user, 
            status='return_rejected'
        )
        
        file = file_request.file
        
        # Get the latest version that was uploaded (the rejected one)
        latest_version = file.versions.filter(file_attachment__isnull=False).order_by('-created_at').first()
        
        return render(request, self.template_name, {
            'file_request': file_request,
            'file': file,
            'latest_version': latest_version
        })
    
    def post(self, request, pk):
        file_request = get_object_or_404(
            FileRequest, 
            pk=pk, 
            requesting_user=request.user, 
            status='return_rejected'
        )
        
        file = file_request.file
        uploaded_file = request.FILES.get('file_attachment')
        notes = request.POST.get('notes', '')
        
        # If file has attachment, require upload
        has_attachment = file.file_attachment or file.versions.filter(file_attachment__isnull=False).exists()
        
        if has_attachment and not uploaded_file:
            messages.error(request, 'You must upload a new document when resubmitting the return.')
            return redirect('file_return_resubmit', pk=pk)
        
        # If new file is uploaded, create a new version
        if uploaded_file:
            version = file.create_version(
                user=request.user,
                change_type='return',
                notes=notes,
                file_attachment=uploaded_file
            )
            # Update the main file attachment
            file.file_attachment = uploaded_file
            file.original_filename = uploaded_file.name
            file.save()
        
        # Re-submit the return
        file_request.resubmit_return(notes=notes)
        
        messages.success(
            request, 
            'Your return has been re-submitted. Registry will verify the new document.'
        )
        return redirect('file_detail', uuid=file.uuid)


class FileReturnVerifyView(LoginRequiredMixin, View):
    """Registry/Admin verifies a file return"""
    template_name = 'register/request_verify_return.html'
    
    def get(self, request, pk):
        # Only registry/admin can verify returns
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to verify returns.')
            return redirect('dashboard')
        
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending_return')
        except FileRequest.DoesNotExist:
            # Check if the request exists at all
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be verified for return. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        except FileRequest.MultipleObjectsReturned:
            messages.error(request, 'An error occurred. Multiple requests found.')
            return redirect('request_list')
        
        # Check if there's a new version with attachment
        latest_version = file_request.file.versions.filter(file_attachment__isnull=False).order_by('-created_at').first()
        
        # Get QR scan result if attachment exists
        qr_result = None
        if latest_version and latest_version.file_attachment:
            try:
                from register.watermark import scan_pdf_for_qr_code
                expected_qr_data = str(file_request.file.uuid)
                qr_result = scan_pdf_for_qr_code(
                    latest_version.file_attachment.path,
                    expected_qr_data
                )
                # Add the expected UUID to the result for display
                qr_result['expected_uuid'] = expected_qr_data
            except Exception as e:
                qr_result = {
                    'found': False,
                    'matched': False,
                    'qr_data': None,
                    'message': f'Error scanning PDF: {str(e)}',
                    'expected_uuid': str(file_request.file.uuid),
                    'error': str(e)
                }
        
        # Check if file has any attachment
        has_attachment = file_request.file.file_attachment or file_request.file.versions.filter(file_attachment__isnull=False).exists()
        
        return render(request, self.template_name, {
            'file_request': file_request,
            'latest_version': latest_version,
            'qr_result': qr_result,
            'has_attachment': has_attachment
        })
    
    def post(self, request, pk):
        # Only registry/admin can verify returns
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to verify returns.')
            return redirect('dashboard')
        
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending_return')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be verified for return. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        except FileRequest.MultipleObjectsReturned:
            messages.error(request, 'An error occurred. Multiple requests found.')
            return redirect('request_list')
        
        condition = request.POST.get('condition', 'good')
        notes = request.POST.get('notes', '')
        
        # Check if there's a new version with attachment
        latest_version = file_request.file.versions.filter(file_attachment__isnull=False).order_by('-created_at').first()
        
        # If there's a new attachment, scan it for QR code
        qr_result = None
        if latest_version and latest_version.file_attachment:
            try:
                # Import the QR scanning function
                from register.watermark import scan_pdf_for_qr_code
                
                # Get expected QR data (file's UUID and reference)
                expected_qr_data = str(file_request.file.uuid)
                
                # Scan the uploaded PDF for QR code
                qr_result = scan_pdf_for_qr_code(
                    latest_version.file_attachment.path,
                    expected_qr_data
                )
                
                # Check if admin wants to force verify despite QR mismatch
                force_verify = request.POST.get('force_verify') == 'on'
                
                # Store QR scan result in notes
                qr_note = f"\n[QR Scan Result: {qr_result['message']}]"
                
                if not qr_result['found']:
                    # No QR code found - could still be valid but warn
                    if not force_verify:
                        notes += qr_note + " WARNING: No QR code found in uploaded document."
                    else:
                        notes += qr_note + " Admin forced verification despite no QR code."
                elif not qr_result['matched']:
                    # QR code found but doesn't match
                    if not force_verify:
                        # Don't auto-reject, just warn and let admin choose
                        notes += qr_note + " WARNING: QR code does not match. "
                        messages.warning(request, f'Warning: QR code mismatch! Use "Force Verify" to verify anyway. {qr_result["message"]}')
                    else:
                        notes += qr_note + " Admin forced verification despite QR mismatch."
                else:
                    # QR code matched
                    notes += qr_note + " QR Code verified successfully."
                    
            except Exception as e:
                # Error during QR scanning - log it and warn but allow verification
                import traceback
                error_msg = f"Error scanning QR: {str(e)}"
                print(traceback.format_exc())
                notes += f"\n[QR Scan Error: {error_msg}]"
                messages.warning(request, f'QR scanning failed: {str(e)}. Please verify document manually.')
        
        # Verify the return
        file_request.verify_return(
            verified_by=request.user,
            condition=condition,
            notes=notes
        )
        
        messages.success(request, f'File return verified! File {file_request.file.reference} is now back in registry.')
        return redirect('request_list')


class FileReturnRejectView(LoginRequiredMixin, View):
    """Registry/Admin rejects a file return (e.g., file is damaged)"""
    template_name = 'register/request_reject_return.html'
    
    def get(self, request, pk):
        # Only registry/admin can reject returns
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to reject returns.')
            return redirect('dashboard')
        
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending_return')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be rejected. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        return render(request, self.template_name, {'file_request': file_request})
    
    def post(self, request, pk):
        # Only registry/admin can reject returns
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to reject returns.')
            return redirect('dashboard')
        
        try:
            file_request = FileRequest.objects.get(pk=pk, status='pending_return')
        except FileRequest.DoesNotExist:
            if FileRequest.objects.filter(pk=pk).exists():
                messages.error(request, 'This request cannot be rejected. It may have already been processed.')
            else:
                messages.error(request, 'File request not found.')
            return redirect('request_list')
        
        reason = request.POST.get('reason', '')
        
        if not reason:
            messages.error(request, 'Please provide a reason for rejecting the return.')
            return render(request, self.template_name, {'file_request': file_request})
        
        # Reject the return
        file_request.reject_return(rejected_by=request.user, reason=reason)
        
        messages.warning(request, f'File return rejected. User has been notified.')
        return redirect('request_list')


class FileListView(LoginRequiredMixin, ListView):
    model = File
    template_name = 'register/file_list.html'
    context_object_name = 'files'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('department', 'current_holder', 'current_department').prefetch_related('tags')
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search) |
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by tag
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__id=tag)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = File.STATUS_CHOICES
        context['overdue_count'] = File.objects.filter(status='overdue').count()
        context['available_tags'] = FileTag.objects.all()
        context['checked_out_count'] = File.objects.filter(status='checked_out').count()
        return context
    
    def get(self, request, *args, **kwargs):
        # Handle CSV export
        if request.GET.get('export') == 'csv':
            from .export_utils import export_files_to_csv
            queryset = self.get_queryset()
            return export_files_to_csv(queryset)
        
        return super().get(request, *args, **kwargs)


class FileDetailView(LoginRequiredMixin, DetailView):
    model = File
    template_name = 'register/file_detail.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['movements'] = self.object.movements.select_related('from_user', 'to_user', 'from_department', 'to_department')[:20]
        context['is_overdue'] = self.object.is_overdue()
        
        # Check if current user has an active request for this file
        if self.request.user.is_authenticated:
            active_request = self.object.checkout_requests.filter(
                requesting_user=self.request.user,
                status__in=['pending', 'approved', 'ready_for_pickup', 'handed_over', 'confirmed', 'pending_return', 'return_rejected', 'returned_verified']
            ).first()
            context['active_request'] = active_request
        
        # Get available tags (not already assigned to this file)
        file_tags = self.object.tags.all()
        context['available_tags'] = FileTag.objects.exclude(pk__in=file_tags)
        
        return context


class FileCreateView(LoginRequiredMixin, View):
    """Create new file - Only registry officers can upload"""
    template_name = 'register/file_upload.html'
    
    def get(self, request):
        # Check if user is registry officer or admin
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'Only registry officers can upload new files.')
            return redirect('dashboard')
        
        form = FileUploadForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        # Check if user is registry officer or admin
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'Only registry officers can upload new files.')
            return redirect('dashboard')
        
        form = FileUploadForm(request.POST, request.FILES)
        form.user = request.user
        
        if form.is_valid():
            file_instance = form.save()
            messages.success(
                request, 
                f'File {file_instance.reference} created successfully. QR Code generated.'
            )
            return redirect('file_detail', uuid=file_instance.uuid)
        
        return render(request, self.template_name, {'form': form})


class CheckoutView(LoginRequiredMixin, View):
    template_name = 'register/checkout.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        if file.status != 'in_registry':
            messages.error(request, f'File is currently {file.get_status_display()}. Cannot check out.')
            return redirect('file_detail', uuid=uuid)
        
        form = CheckoutForm()
        return render(request, self.template_name, {
            'file': file,
            'form': form
        })
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        form = CheckoutForm(request.POST)
        
        if form.is_valid():
            # Verify signature (in production, use proper authentication)
            confirmation = form.cleaned_data['signature_confirmation']
            
            # Create movement record with signature
            movement = FileMovement.objects.create(
                file=file,
                action='checkout',
                from_user=file.created_by or request.user,
                to_user=request.user,
                from_department=file.department,
                to_department=form.cleaned_data['department'],
                notes=f"Purpose: {form.cleaned_data.get('purpose', '')}\n"
                      f"Recipient: {form.cleaned_data['recipient_name']} "
                      f"({form.cleaned_data['recipient_designation']})",
                signature_data=confirmation,
                signed_at=timezone.now()
            )
            
            # Update file status
            file.check_out(
                user=request.user,
                department=form.cleaned_data['department'],
                notes=movement.notes
            )
            
            messages.success(
                request, 
                f'File {file.reference} checked out to {form.cleaned_data["department"]}. '
                f'Due date: {file.due_date.strftime("%Y-%m-%d")}'
            )
            
            # Trigger webhook
            try:
                from register.webhook_service import WebhookService
                WebhookService.trigger_file_checkout(file, request.user)
            except Exception:
                pass
            
            return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {'file': file, 'form': form})


class CheckinView(LoginRequiredMixin, View):
    template_name = 'register/checkin.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        if file.status != 'checked_out' and file.status != 'overdue':
            messages.error(request, 'File is not currently checked out.')
            return redirect('file_detail', uuid=uuid)
        
        # Check if file has attachment - if so, upload is required
        has_attachment = file.file_attachment or file.versions.filter(file_attachment__isnull=False).exists()
        
        form = CheckinForm()
        return render(request, self.template_name, {
            'file': file,
            'form': form,
            'days_out': (timezone.now() - file.checked_out_at).days if file.checked_out_at else 0,
            'has_attachment': has_attachment
        })
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        form = CheckinForm(request.POST, request.FILES)
        
        # Check if file has attachment - if so, upload is required
        has_attachment = file.file_attachment or file.versions.filter(file_attachment__isnull=False).exists()
        uploaded_file = request.FILES.get('file_attachment')
        
        if has_attachment and not uploaded_file:
            messages.error(request, 'This file has a document attachment. You must upload the document when returning the file.')
            return render(request, self.template_name, {
                'file': file,
                'form': form,
                'days_out': (timezone.now() - file.checked_out_at).days if file.checked_out_at else 0,
                'has_attachment': has_attachment
            })
        
        if form.is_valid():
            confirmation = form.cleaned_data['signature_confirmation']
            
            # Create return movement record
            FileMovement.objects.create(
                file=file,
                action='checkin',
                from_user=file.current_holder,
                to_user=request.user,
                from_department=file.current_department,
                to_department=file.department,
                notes=f"Condition: {form.cleaned_data['condition']}\n"
                      f"Return notes: {form.cleaned_data.get('notes', '')}",
                signature_data=confirmation,
                signed_at=timezone.now()
            )
            
            # If file is uploaded, create a new version
            if uploaded_file:
                version = file.create_version(
                    user=request.user,
                    change_type='return',
                    notes=form.cleaned_data.get('notes', ''),
                    file_attachment=uploaded_file
                )
                # Update the main file attachment
                file.file_attachment = uploaded_file
                file.original_filename = uploaded_file.name
                file.save()
            
            # Check if there's an active request that has been confirmed (user has the file)
            # Status must be 'confirmed' meaning user already confirmed receipt and now wants to return
            from register.models import FileRequest
            active_request = FileRequest.objects.filter(
                file=file,
                requesting_user=request.user,
                status='confirmed'  # Only for confirmed requests - user already has the file
            ).first()
            
            if active_request:
                # Use the proper return flow with admin verification
                active_request.initiate_return(notes=form.cleaned_data.get('notes', ''))
                messages.success(request, f'File {file.reference} return submitted for verification. Registry will confirm the return.')
                return redirect('file_detail', uuid=uuid)
            else:
                # No active confirmed request - direct check-in
                # This handles cases where file was checked out directly without a request
                file.check_in(user=request.user, notes=form.cleaned_data['notes'])
                messages.success(request, f'File {file.reference} returned to registry.')
                
                # Trigger webhook
                try:
                    from register.webhook_service import WebhookService
                    WebhookService.trigger_file_checkin(file, request.user)
                except Exception:
                    pass
                
                return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {
            'file': file,
            'form': form,
            'days_out': (timezone.now() - file.checked_out_at).days if file.checked_out_at else 0,
            'has_attachment': has_attachment
        })


class OverdueListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'register/overdue_list.html'
    context_object_name = 'overdue_files'
    permission_required = 'register.view_file'
    
    def get_queryset(self):
        # Auto-mark overdue files first
        checked_out = File.objects.filter(status='checked_out')
        for file in checked_out:
            file.mark_overdue()
        
        return File.objects.filter(
            Q(status='overdue') | 
            Q(status='checked_out', due_date__lt=timezone.now())
        ).select_related('department', 'current_holder', 'current_department')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_overdue'] = len(self.object_list)
        context['critical_overdue'] = sum(
            1 for f in self.object_list 
            if f.due_date and (timezone.now() - f.due_date).days > 14
        )
        return context


class AuditReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'register.view_filemovement'
    
    def get(self, request):
        form = AuditFilterForm(request.GET)
        movements = FileMovement.objects.select_related(
            'file', 'from_user', 'to_user', 'from_department', 'to_department'
        )
        
        if form.is_valid():
            if form.cleaned_data.get('department'):
                movements = movements.filter(
                    Q(from_department=form.cleaned_data['department']) |
                    Q(to_department=form.cleaned_data['department'])
                )
            
            if form.cleaned_data.get('date_from'):
                movements = movements.filter(created_at__date__gte=form.cleaned_data['date_from'])
            
            if form.cleaned_data.get('date_to'):
                movements = movements.filter(created_at__date__lte=form.cleaned_data['date_to'])
            
            if form.cleaned_data.get('status'):
                movements = movements.filter(file__status=form.cleaned_data['status'])
        
        # PDF Export
        if request.GET.get('export') == 'pdf':
            return self.export_pdf(movements, form.cleaned_data)
        
        context = {
            'form': form,
            'movements': movements[:100],
            'total_count': movements.count()
        }
        return render(request, 'register/audit_report.html', context)
    
    def export_pdf(self, movements, filters):
        """Generate PDF audit report"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=20
        )
        
        # Title
        elements.append(Paragraph("File Movement Audit Report", title_style))
        elements.append(Paragraph(
            f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Total Records: {movements.count()}",
            styles['Normal']
        ))
        elements.append(Spacer(1, 20))
        
        # Filter info
        filter_text = []
        if filters.get('department'):
            filter_text.append(f"Department: {filters['department']}")
        if filters.get('date_from'):
            filter_text.append(f"From: {filters['date_from']}")
        if filters.get('date_to'):
            filter_text.append(f"To: {filters['date_to']}")
        
        if filter_text:
            elements.append(Paragraph("Filters: " + " | ".join(filter_text), styles['Italic']))
            elements.append(Spacer(1, 10))
        
        # Table data
        data = [['Date', 'Reference', 'Action', 'From', 'To', 'Department', 'Signature']]
        
        for move in movements[:500]:  # Limit to 500 for PDF performance
            data.append([
                move.created_at.strftime('%Y-%m-%d %H:%M'),
                move.file.reference,
                move.get_action_display(),
                move.from_user.get_full_name() if move.from_user else 'System',
                move.to_user.get_full_name() if move.to_user else 'Unknown',
                f"{move.from_department} → {move.to_department}" if move.from_department and move.to_department else 'N/A',
                '✓' if move.signature_data else '-'
            ])
        
        # Create table
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        response = FileResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="audit_report_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response


class QRCodeView(LoginRequiredMixin, View):
    """View to display/print QR code for physical attachment"""
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        return render(request, 'register/qr_print.html', {'file': file})


class FilePreviewView(LoginRequiredMixin, View):
    """View to preview file attachment in browser"""
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        if not file.file_attachment:
            return HttpResponseNotFound("No file attachment found")
        
        # Open and serve the file
        try:
            fs = FileSystemStorage()
            path = file.file_attachment.path
            
            if fs.exists(path):
                with fs.open(path, 'rb') as f:
                    content = f.read()
                
                # Detect content type based on file extension
                import mimetypes
                content_type, _ = mimetypes.guess_type(file.original_filename)
                
                # Fallback to octet-stream if content type is None
                if content_type is None:
                    content_type = 'application/octet-stream'
                
                response = HttpResponse(content, content_type=content_type)
                response['Content-Disposition'] = f'inline; filename="{file.original_filename}"'
                return response
            else:
                return HttpResponseNotFound("File not found on disk")
        except Exception as e:
            return HttpResponse(f"Error loading file: {str(e)}", status=500)


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        # Get user-specific data
        user = request.user
        from django.db.models import Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Base file counts
        total_files = File.objects.count()
        in_registry = File.objects.filter(status='in_registry').count()
        checked_out = File.objects.filter(status='checked_out').count()
        overdue = File.objects.filter(status='overdue').count()
        archived = File.objects.filter(status='archived').count()
        
        # File status distribution for charts
        file_status_data = {
            'in_registry': in_registry,
            'checked_out': checked_out,
            'overdue': overdue,
            'archived': archived,
        }
        
        # Request statistics
        total_requests = FileRequest.objects.count()
        pending_requests = FileRequest.objects.filter(status='pending').count()
        approved_requests = FileRequest.objects.filter(status='approved').count()
        handed_over_requests = FileRequest.objects.filter(status='handed_over').count()
        returned_requests = FileRequest.objects.filter(status='returned_verified').count()
        rejected_requests = FileRequest.objects.filter(status='rejected').count()
        
        # Request status distribution for charts
        request_status_data = {
            'pending': pending_requests,
            'approved': approved_requests,
            'handed_over': handed_over_requests,
            'returned': returned_requests,
            'rejected': rejected_requests,
        }
        
        # Monthly file creation trend (last 6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_files = []
        for i in range(6):
            month_start = (timezone.now() - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if i == 0:
                month_end = timezone.now()
            else:
                month_end = month_start + timedelta(days=32)
                month_end = month_end.replace(day=1)
            
            count = File.objects.filter(created_at__gte=month_start, created_at__lt=month_end).count()
            month_name = month_start.strftime('%b')
            monthly_files.append({'month': month_name, 'count': count})
        monthly_files.reverse()
        
        # Monthly request trend
        monthly_requests = []
        for i in range(6):
            month_start = (timezone.now() - timedelta(days=30*i)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if i == 0:
                month_end = timezone.now()
            else:
                month_end = month_start + timedelta(days=32)
                month_end = month_end.replace(day=1)
            
            count = FileRequest.objects.filter(created_at__gte=month_start, created_at__lt=month_end).count()
            month_name = month_start.strftime('%b')
            monthly_requests.append({'month': month_name, 'count': count})
        monthly_requests.reverse()
        
        # Department statistics
        dept_stats = []
        for dept in Department.objects.filter(is_active=True)[:10]:
            file_count = File.objects.filter(department=dept).count()
            checked = File.objects.filter(department=dept, status='checked_out').count()
            overdue_count = File.objects.filter(department=dept, status='overdue').count()
            request_count = FileRequest.objects.filter(requesting_department=dept).count()
            dept_stats.append({
                'name': dept.name,
                'file_count': file_count,
                'checked_out': checked,
                'overdue': overdue_count,
                'requests': request_count
            })
        
        # User activity - files checked out per user
        top_users = []
        from django.db.models import Count
        user_checkouts = File.objects.filter(
            current_holder__isnull=False
        ).values('current_holder__username').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Activity log summary
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        activity_today = ActivityLog.objects.filter(timestamp__date=today).count()
        activity_week = ActivityLog.objects.filter(timestamp__date__gte=week_ago).count()
        
        # Recent activity breakdown by type
        activity_by_type = {}
        for action_type, _ in ActivityLog.ACTION_TYPES:
            count = ActivityLog.objects.filter(action=action_type).count()
            if count > 0:
                activity_by_type[action_type] = count
        
        # User's files checked out
        my_checked_out = []
        if hasattr(user, 'profile'):
            my_checked_out = File.objects.filter(current_holder=user)
        
        # User's pending requests
        my_requests = []
        if user.is_authenticated:
            my_requests = FileRequest.objects.filter(
                requesting_user=user,
                status__in=['pending', 'ready_for_pickup', 'handed_over']
            ).select_related('file', 'file__department')
        
        # Pending requests for registry/admin
        pending_approvals = []
        ready_for_pickup = []
        pending_returns = []
        is_registry_or_admin = False
        
        # Check if user is admin or registry
        if user.is_superuser:
            is_registry_or_admin = True
        elif hasattr(user, 'profile') and user.profile.role in ['registry', 'admin']:
            is_registry_or_admin = True
        
        if is_registry_or_admin:
            # Show all requests that need admin/registry action
            pending_approvals = FileRequest.objects.filter(
                status='pending'
            ).select_related('file', 'requesting_user', 'requesting_department')[:5]
            
            # Also show ready_for_pickup requests that need handover
            ready_for_pickup = FileRequest.objects.filter(
                status='ready_for_pickup'
            ).select_related('file', 'requesting_user', 'requesting_department')[:5]
            
            # Also show pending_return requests that need verification
            pending_returns = FileRequest.objects.filter(
                status='pending_return'
            ).select_related('file', 'requesting_user', 'requesting_department')[:5]
        
        context = {
            # File statistics
            'total_files': total_files,
            'in_registry': in_registry,
            'checked_out': checked_out,
            'overdue': overdue,
            'archived': archived,
            'file_status_data': file_status_data,
            
            # Request statistics
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'approved_requests': approved_requests,
            'handed_over_requests': handed_over_requests,
            'returned_requests': returned_requests,
            'rejected_requests': rejected_requests,
            'request_status_data': request_status_data,
            
            # Monthly trends
            'monthly_files': monthly_files,
            'monthly_requests': monthly_requests,
            
            # Department stats
            'dept_stats': dept_stats,
            
            # User activity
            'top_users': list(user_checkouts),
            'activity_today': activity_today,
            'activity_week': activity_week,
            'activity_by_type': activity_by_type,
            
            # Lists
            'recent_movements': FileMovement.objects.select_related('file', 'from_user', 'to_user', 'from_department', 'to_department')[:10],
            'department_stats': Department.objects.annotate(
                file_count=Count('files'),
                active_count=Count('active_files')
            ).order_by('-file_count')[:5],
            'my_checked_out': my_checked_out,
            'my_requests': my_requests,
            'pending_approvals': pending_approvals,
            'ready_for_pickup': ready_for_pickup,
            'pending_returns': pending_returns,
            'total_departments': Department.objects.filter(is_active=True).count(),
            'archived_files': archived,
            
            # Flags
            'is_registry_or_admin': is_registry_or_admin,
        }
        return render(request, 'register/dashboard.html', context)


class AccountSettingsView(LoginRequiredMixin, View):
    """User account settings - view and update profile"""
    template_name = 'register/account_settings.html'
    
    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        # Pass admin_user to form so it can determine which fields to show
        form = UserProfileForm(instance=profile, admin_user=user) if profile else None
        return render(request, self.template_name, {
            'form': form,
            'user': user
        })
    
    def post(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        
        if profile:
            # Pass admin_user to form
            form = UserProfileForm(request.POST, instance=profile, admin_user=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('account_settings')
        else:
            form = UserProfileForm(request.POST, admin_user=user)
            
        return render(request, self.template_name, {'form': form, 'user': user})


class ChangePasswordView(LoginRequiredMixin, View):
    """User change password view"""
    template_name = 'register/change_password.html'
    
    def get(self, request):
        form = PasswordChangeForm(user=request.user)
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            # Re-authenticate with new password to maintain session
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, form.user)
            messages.success(request, 'Password changed successfully!')
            return redirect('account_settings')
        return render(request, self.template_name, {'form': form})


class ActivityLogListView(LoginRequiredMixin, ListView):
    """View activity logs - admin/registry only"""
    model = ActivityLog
    template_name = 'register/activity_log_list.html'
    context_object_name = 'activities'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user').all()
        
        # Filter by user
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action type
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_choices'] = ActivityLog.ACTION_TYPES
        context['users'] = User.objects.filter(is_active=True)
        return context
    
    def get(self, request, *args, **kwargs):
        # Handle CSV export
        if request.GET.get('export') == 'csv':
            from .export_utils import export_activity_to_csv
            queryset = self.get_queryset()
            return export_activity_to_csv(queryset)
        
        return super().get(request, *args, **kwargs)


class AuditTrailView(LoginRequiredMixin, ListView):
    """Visual timeline view of activity logs - Admin/Registry only"""
    model = ActivityLog
    template_name = 'register/audit_trail.html'
    context_object_name = 'activities'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is admin or registry
        if not (request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )):
            messages.error(request, 'You do not have permission to view the audit trail.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = ActivityLog.objects.select_related('user').order_by('-timestamp')
        
        # Filter by user
        user_id = self.request.GET.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action type
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_choices'] = ActivityLog.ACTION_TYPES
        context['users'] = User.objects.filter(is_active=True)
        return context


class MyActivityView(LoginRequiredMixin, ListView):
    """View own activity log"""
    model = ActivityLog
    template_name = 'register/my_activity.html'
    context_object_name = 'activities'
    paginate_by = 20
    
    def get_queryset(self):
        return ActivityLog.objects.filter(user=self.request.user)


class FileArchiveView(LoginRequiredMixin, View):
    """Archive a file - registry/admin only"""
    template_name = 'register/file_archive.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to archive files.')
            return redirect('file_detail', uuid=uuid)
        
        if file.status not in ['in_registry']:
            messages.error(request, 'Cannot archive a file that is checked out.')
            return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {'file': file})
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        reason = request.POST.get('reason', '')
        
        success, message = file.archive(request.user, reason)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        
        return redirect('file_detail', uuid=uuid)


class FileRestoreView(LoginRequiredMixin, View):
    """Restore a file from archive - registry/admin only"""
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to restore files.')
            return redirect('file_detail', uuid=uuid)
        
        success, message = file.restore_from_archive(request.user)
        
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        
        return redirect('file_detail', uuid=uuid)


class FileVersionHistoryView(LoginRequiredMixin, View):
    """View file version history"""
    template_name = 'register/file_versions.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        versions = file.versions.all()
        
        return render(request, self.template_name, {
            'file': file,
            'versions': versions
        })


class TagListView(LoginRequiredMixin, ListView):
    """List all tags (admin/registry only)"""
    model = FileTag
    template_name = 'register/tag_list.html'
    context_object_name = 'tags'
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to manage tags.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return FileTag.objects.annotate(file_count=Count('files'))


class TagCreateView(LoginRequiredMixin, CreateView):
    """Create new tag (admin/registry only)"""
    model = FileTag
    form_class = FileTagForm
    template_name = 'register/tag_form.html'
    success_url = reverse_lazy('tag_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to create tags.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Tag created successfully!')
        return super().form_valid(form)


class TagUpdateView(LoginRequiredMixin, UpdateView):
    """Update tag (admin/registry only)"""
    model = FileTag
    form_class = FileTagForm
    template_name = 'register/tag_form.html'
    success_url = reverse_lazy('tag_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to edit tags.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Tag updated successfully!')
        return super().form_valid(form)


class TagDeleteView(LoginRequiredMixin, DeleteView):
    """Delete tag (admin/registry only)"""
    model = FileTag
    template_name = 'register/tag_confirm_delete.html'
    success_url = reverse_lazy('tag_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or 
                (hasattr(request.user, 'profile') and 
                 request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to delete tags.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Tag deleted successfully!')
        return super().form_valid(form)


@login_required
def add_tag_to_file(request, uuid):
    """Add a tag to a file - Admin/Registry only"""
    # Check if user is admin or registry
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'profile') and 
             request.user.profile.role in ['registry', 'admin'])):
        messages.error(request, 'You do not have permission to add tags to files.')
        return redirect('file_detail', uuid=uuid)
    
    file = get_object_or_404(File, uuid=uuid)
    
    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        tag = get_object_or_404(FileTag, pk=tag_id)
        file.tags.add(tag)
        messages.success(request, f'Tag "{tag.name}" added to file.')
    
    return redirect('file_detail', uuid=uuid)


@login_required
def remove_tag_from_file(request, uuid):
    """Remove a tag from a file - Admin/Registry only"""
    # Check if user is admin or registry
    if not (request.user.is_superuser or 
            (hasattr(request.user, 'profile') and 
             request.user.profile.role in ['registry', 'admin'])):
        messages.error(request, 'You do not have permission to remove tags from files.')
        return redirect('file_detail', uuid=uuid)
    
    file = get_object_or_404(File, uuid=uuid)
    
    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        tag = get_object_or_404(FileTag, pk=tag_id)
        file.tags.remove(tag)
        messages.success(request, f'Tag "{tag.name}" removed from file.')
    
    return redirect('file_detail', uuid=uuid)


@login_required
def qr_scan_lookup(request):
    """
    QR Code Scan Lookup - Find file by UUID from scanned QR code
    This view handles the QR code scanned/entered to look up a file
    """
    template_name = 'register/qr_scan.html'
    
    if request.method == 'POST':
        uuid_input = request.POST.get('uuid', '').strip()
        
        if not uuid_input:
            messages.error(request, 'Please enter or scan a QR code value.')
            return render(request, template_name)
        
        # Try to find file by UUID
        try:
            file = File.objects.get(uuid=uuid_input)
            # Redirect to the file's detail page or version upload
            return redirect('file_return_upload', uuid=file.uuid)
        except File.DoesNotExist:
            messages.error(request, f'No file found with ID: {uuid_input}')
            return render(request, template_name)
    
    return render(request, template_name)


@login_required
def file_return_upload(request, uuid):
    """
    File Return Upload - Upload a new version when document is returned
    After scanning QR code, user uploads the document which creates a new version
    """
    file = get_object_or_404(File, uuid=uuid)
    template_name = 'register/file_return.html'
    
    # Get the previous version for comparison
    previous_version = file.versions.first()
    
    if request.method == 'POST':
        new_file = request.FILES.get('file_attachment')
        notes = request.POST.get('notes', '')
        changes_summary = request.POST.get('changes_summary', '')
        employee_id = request.POST.get('employee_id', '').strip()
        
        if not new_file:
            messages.error(request, 'Please upload a document file.')
            return render(request, template_name, {'file': file, 'previous_version': previous_version})
        
        # Validate employee ID - must match current user's profile
        if not employee_id:
            messages.error(request, 'Please enter your Employee ID (Confirmation Number).')
            return render(request, template_name, {'file': file, 'previous_version': previous_version})
        
        # Get user's profile employee_id
        user_employee_id = None
        try:
            if hasattr(request.user, 'profile') and request.user.profile:
                user_employee_id = request.user.profile.employee_id
        except Exception:
            pass
        
        # Also check User model directly
        if not user_employee_id:
            # Try to get from related profile model
            from register.models import UserProfile
            try:
                profile = UserProfile.objects.get(user=request.user)
                user_employee_id = profile.employee_id
            except UserProfile.DoesNotExist:
                pass
        
        # Validate that the entered employee_id matches the user's profile
        if user_employee_id:
            if employee_id != user_employee_id:
                messages.error(request, f'Employee ID does not match your profile. Please enter your correct Employee ID.')
                return render(request, template_name, {'file': file, 'previous_version': previous_version})
        else:
            # If user doesn't have an employee_id in profile, check if they have one registered
            # For now, allow if they don't have employee_id set (backwards compatibility)
            messages.warning(request, 'Note: Your profile does not have an Employee ID registered. Please contact registry to update your profile.')
        
        # Create new version
        version = file.create_version(
            user=request.user,
            change_type='update',
            notes=notes,
            changes_summary=changes_summary,
            file_attachment=new_file
        )
        
        # Update the main file attachment
        file.file_attachment = new_file
        file.original_filename = new_file.name
        file.save()
        
        # Compare with previous version
        if previous_version:
            differences, _ = file.compare_versions(previous_version.id, version.id)
            if differences:
                version.changes_summary = '; '.join(differences)
                version.save()
            messages.success(request, f'Version {version.version_number} created successfully!')
        else:
            messages.success(request, f'File uploaded as Version {version.version_number}!')
        
        return redirect('file_versions', uuid=file.uuid)
    
    # Get user's employee_id for display
    user_employee_id = None
    try:
        if hasattr(request.user, 'profile') and request.user.profile:
            user_employee_id = request.user.profile.employee_id
    except Exception:
        pass
    
    # Also check UserProfile model directly
    if not user_employee_id:
        from register.models import UserProfile
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_employee_id = profile.employee_id
        except UserProfile.DoesNotExist:
            pass
    
    context = {
        'file': file,
        'previous_version': previous_version,
        'user_employee_id': user_employee_id,
    }
    return render(request, template_name, context)


@login_required
def version_compare(request, uuid, v1_id, v2_id):
    """Compare two versions of a file"""
    file = get_object_or_404(File, uuid=uuid)
    template_name = 'register/version_compare.html'
    
    differences, error = file.compare_versions(v1_id, v2_id)
    
    if error:
        messages.error(request, error)
        return redirect('file_versions', uuid=uuid)
    
    v1 = file.versions.get(id=v1_id)
    v2 = file.versions.get(id=v2_id)
    
    context = {
        'file': file,
        'v1': v1,
        'v2': v2,
        'differences': differences,
    }
    return render(request, template_name, context)


@login_required
def my_accessible_files(request):
    """
    Show files the user has been permitted to access
    - For registry/admin: all files
    - For regular users: approved requests, checked out files, pending requests
    """
    user = request.user
    
    # Check if user is registry or admin
    is_registry_or_admin = user.is_superuser
    if not is_registry_or_admin:
        try:
            if hasattr(user, 'profile') and user.profile:
                if user.profile.role in ['registry', 'admin']:
                    is_registry_or_admin = True
        except Exception:
            pass
    
    if is_registry_or_admin:
        # Registry/Admin can see all files
        all_files = File.objects.select_related('department', 'current_holder', 'created_by').order_by('-created_at')
        
        context = {
            'all_files': all_files,
            'is_admin': True,
            'approved_requests': FileRequest.objects.none(),
            'checked_out_files': File.objects.none(),
            'pending_requests': FileRequest.objects.none(),
        }
    else:
        # Regular users see only their permitted files
        # Files the user has been approved to access (including returned files)
        # Include all statuses except pending, rejected, and cancelled
        approved_requests = FileRequest.objects.filter(
            requesting_user=user,
            status__in=['approved', 'ready_for_pickup', 'handed_over', 'confirmed', 'returned_verified', 'pending_return', 'return_rejected']
        ).select_related('file', 'file__department')
        
        # Files checked out to this user
        checked_out_files = File.objects.filter(
            current_holder=user,
            status='checked_out'
        ).select_related('department')
        
        # User's pending requests
        pending_requests = FileRequest.objects.filter(
            requesting_user=user,
            status='pending'
        ).select_related('file', 'file__department')
        
        context = {
            'approved_requests': approved_requests,
            'checked_out_files': checked_out_files,
            'pending_requests': pending_requests,
            'is_admin': False,
            'all_files': File.objects.none(),
        }
    
    return render(request, 'register/my_accessible_files.html', context)


@login_required
def file_download(request, uuid):
    """
    Download a file if the user has permission to access it.
    Permission is granted if user is:
    - The current holder
    - Has an approved request for this file
    - Is the creator of the file
    - Is an admin/registry user
    
    For PDF files, a QR code watermark is added on download.
    """
    from django.http import HttpResponse
    from django.conf import settings
    import io
    
    # Import watermark function
    from register.watermark import add_qr_watermark_to_pdf_bytes
    
    # Get logger
    _logger = logging.getLogger(__name__)
    
    file = get_object_or_404(File, uuid=uuid)
    
    # Check if user has permission to download
    has_permission = False
    restricted_to_approved_version = False
    approved_version = None
    
    # User is current holder
    if file.current_holder == request.user:
        has_permission = True
    
    # User has approved request (active - can get latest version)
    elif FileRequest.objects.filter(
        file=file,
        requesting_user=request.user,
        status__in=['ready_for_pickup', 'handed_over', 'confirmed', 'pending_return']
    ).exists():
        has_permission = True
    
    # User has returned the file - restrict to approved version only
    elif FileRequest.objects.filter(
        file=file,
        requesting_user=request.user,
        status__in=['returned_verified', 'return_rejected']
    ).exists():
        has_permission = True
        restricted_to_approved_version = True
        # Get the approved version for this request
        file_request = FileRequest.objects.filter(
            file=file,
            requesting_user=request.user,
            status__in=['returned_verified', 'return_rejected']
        ).first()
        if file_request and file_request.approved_version:
            approved_version = file_request.approved_version
    
    # User is the creator
    elif file.created_by == request.user:
        has_permission = True
    
    # User is admin or registry
    elif request.user.is_superuser:
        has_permission = True
    else:
        # Check for registry/admin role
        try:
            if hasattr(request.user, 'profile') and request.user.profile:
                if request.user.profile.role in ['registry', 'admin']:
                    has_permission = True
        except Exception:
            pass
    
    if not has_permission:
        messages.error(request, 'You do not have permission to download this file.')
        return redirect('file_detail', uuid=uuid)
    
    # Determine which file to use and version info
    version = None
    
    # If restricted to approved version, use that version
    if restricted_to_approved_version and approved_version:
        version = approved_version
    elif not file.file_attachment:
        # Check if there's a version with attachment
        version = file.versions.filter(file_attachment__isnull=False).first()
        if not version:
            messages.error(request, 'No file attached to this document.')
            return redirect('file_detail', uuid=uuid)
    
    # Prepare file info for watermark
    file_info = {
        'reference': file.reference,
        'title': file.title,
        'downloaded_by': request.user.get_full_name() or request.user.username,
    }
    
    # Get QR code path
    qr_code_path = None
    if file.qr_code:
        try:
            qr_code_path = file.qr_code.path
            # Verify the file exists on disk
            if os.path.exists(qr_code_path):
                _logger.info(f"QR code found at: {qr_code_path}")
            else:
                _logger.error(f"QR code path exists in DB but file not found on disk: {qr_code_path}")
                qr_code_path = None
        except Exception as e:
            _logger.error(f"Error getting QR code path: {str(e)}")
    
    # Check if file has attachment and is PDF
    if version:
        file_path = version.file_attachment.path
        file_name = version.original_filename or version.file_attachment.name
        is_pdf = file_name.lower().endswith('.pdf')
    else:
        file_path = file.file_attachment.path
        file_name = file.original_filename or file.file_attachment.name
        is_pdf = file_name.lower().endswith('.pdf')
    
    # Log the download activity
    ActivityLog.objects.create(
        user=request.user,
        action='file_download',
        description=f'Downloaded file: {file.reference}' + (f' (Version {version.version_number})' if version else ''),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Serve the file
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    _logger.info(f"DOWNLOAD DEBUG - is_pdf: {is_pdf}, qr_code_path: {qr_code_path}")

    # Add QR watermark to PDF if applicable
    watermarked_pdf = None
    if is_pdf and qr_code_path:
        _logger.info(f"Starting watermark process for file: {file_name}")
        try:
            watermarked_pdf = add_qr_watermark_to_pdf_bytes(
                io.BytesIO(file_content),
                qr_code_path,
                file_info=file_info,
                position='bottom-right'
            )
        except Exception as e:
            _logger.error(f"Exception in watermark function: {str(e)}")
        
        if watermarked_pdf:
            file_content = watermarked_pdf.getvalue()
            base_name, ext = os.path.splitext(file_name)
            file_name = f"{base_name}_watermarked{ext}"
            _logger.info(f"Successfully watermarked PDF")
        else:
            _logger.error("Watermark returned None - QR code may not have been embedded")
    
    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class FileCommentView(LoginRequiredMixin, View):
    """Add/view comments on a file"""
    template_name = 'register/file_comments.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        # Get comments - hide internal comments from non-privileged users
        if request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        ):
            comments = file.comments.select_related('author').all()
        else:
            comments = file.comments.select_related('author').filter(is_internal=False)
        
        return render(request, self.template_name, {
            'file': file,
            'comments': comments,
        })
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        # Check if user can comment
        can_add_internal = request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )
        
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, 'Comment cannot be empty.')
            return redirect('file_comments', uuid=uuid)
        
        is_internal = request.POST.get('is_internal') == 'on' and can_add_internal
        
        # Create comment
        FileComment.objects.create(
            file=file,
            author=request.user,
            content=content,
            is_internal=is_internal
        )
        
        messages.success(request, 'Comment added successfully.')
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action='comment_added',
            description=f"Added comment to file: {file.reference}",
            ip_address=get_client_ip(request)
        )
        
        return redirect('file_comments', uuid=uuid)
