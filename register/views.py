import io
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

from .models import File, FileMovement, Department, UserProfile, Notification, FileRequest, ActivityLog, FileVersion, FileTag
from django.contrib.auth.models import User
from .forms import (
    FileUploadForm, CheckoutForm, CheckinForm, AuditFilterForm,
    UserRegistrationForm, UserProfileForm, DepartmentForm,
    FileRequestForm, FileRequestApprovalForm, FileHandoverForm, UserConfirmationForm,
    FileTagForm
)


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
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
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
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            # Department users only see their own requests
            requests = FileRequest.objects.filter(
                requesting_user=request.user
            ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            pending_count = 0
        else:
            # Registry and admin see all pending requests
            status_filter = request.GET.get('status', 'pending')
            requests = FileRequest.objects.filter(
                status=status_filter
            ).select_related('file', 'requesting_user', 'requesting_department', 'processed_by')
            pending_count = FileRequest.objects.filter(status='pending').count()
        
        return render(request, self.template_name, {
            'requests': requests,
            'current_status': request.GET.get('status', 'pending'),
            'pending_count': pending_count
        })


class FileRequestProcessView(LoginRequiredMixin, View):
    """Process file request (approve/reject) - Registry only"""
    template_name = 'register/request_process.html'
    
    def get(self, request, pk):
        file_request = get_object_or_404(FileRequest, pk=pk, status='pending')
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to process requests.')
            return redirect('request_list')
        
        form = FileRequestApprovalForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        file_request = get_object_or_404(FileRequest, pk=pk, status='pending')
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
        file_request = get_object_or_404(FileRequest, pk=pk, status='ready_for_pickup')
        
        # Check permission
        if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role in ['registry', 'admin'])):
            messages.error(request, 'You do not have permission to handover files.')
            return redirect('request_list')
        
        form = FileHandoverForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        file_request = get_object_or_404(FileRequest, pk=pk, status='ready_for_pickup')
        form = FileHandoverForm(request.POST)
        
        if form.is_valid():
            # Verify confirmation code matches requesting user's employee ID
            expected_code = file_request.requesting_user.profile.employee_id if hasattr(file_request.requesting_user, 'profile') else ''
            
            if form.cleaned_data['confirmation_code'] != expected_code:
                messages.error(request, 'Invalid confirmation code.')
                return render(request, self.template_name, {'file_request': file_request, 'form': form})
            
            # Update file status and create movement
            file_request.file.check_out(
                user=file_request.requesting_user,
                department=file_request.requesting_department,
                notes=f"Handover confirmed. Registry: {request.user.get_full_name()}"
            )
            
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
        file_request = get_object_or_404(FileRequest, pk=pk, requesting_user=request.user, status='handed_over')
        form = UserConfirmationForm()
        return render(request, self.template_name, {'file_request': file_request, 'form': form})
    
    def post(self, request, pk):
        file_request = get_object_or_404(FileRequest, pk=pk, requesting_user=request.user, status='handed_over')
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
                status__in=['pending', 'approved', 'ready_for_pickup', 'handed_over']
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
        
        form = FileUploadForm(request.POST)
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
            return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {'file': file, 'form': form})


class CheckinView(LoginRequiredMixin, View):
    template_name = 'register/checkin.html'
    
    def get(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        
        if file.status != 'checked_out' and file.status != 'overdue':
            messages.error(request, 'File is not currently checked out.')
            return redirect('file_detail', uuid=uuid)
        
        form = CheckinForm()
        return render(request, self.template_name, {
            'file': file,
            'form': form,
            'days_out': (timezone.now() - file.checked_out_at).days if file.checked_out_at else 0
        })
    
    def post(self, request, uuid):
        file = get_object_or_404(File, uuid=uuid)
        form = CheckinForm(request.POST)
        
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
            
            file.check_in(user=request.user, notes=form.cleaned_data['notes'])
            
            messages.success(request, f'File {file.reference} returned to registry.')
            return redirect('file_detail', uuid=uuid)
        
        return render(request, self.template_name, {
            'file': file,
            'form': form,
            'days_out': (timezone.now() - file.checked_out_at).days if file.checked_out_at else 0
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


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        # Get user-specific data
        user = request.user
        
        # Base file counts
        total_files = File.objects.count()
        in_registry = File.objects.filter(status='in_registry').count()
        checked_out = File.objects.filter(status='checked_out').count()
        overdue = File.objects.filter(status='overdue').count()
        
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
        if hasattr(user, 'profile') and user.profile.role in ['registry', 'admin']:
            pending_approvals = FileRequest.objects.filter(
                status='pending'
            ).select_related('file', 'requesting_user', 'requesting_department')[:5]
        
        context = {
            'total_files': total_files,
            'in_registry': in_registry,
            'checked_out': checked_out,
            'overdue': overdue,
            'recent_movements': FileMovement.objects.select_related('file', 'from_user', 'to_user', 'from_department', 'to_department')[:10],
            'department_stats': Department.objects.annotate(
                file_count=Count('files'),
                active_count=Count('active_files')
            ).order_by('-file_count')[:5],
            'my_checked_out': my_checked_out,
            'my_requests': my_requests,
            'pending_approvals': pending_approvals,
            'total_departments': Department.objects.filter(is_active=True).count(),
            'archived_files': File.objects.filter(status='archived').count(),
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
    """List all tags (admin only)"""
    model = FileTag
    template_name = 'register/tag_list.html'
    context_object_name = 'tags'
    
    def get_queryset(self):
        return FileTag.objects.annotate(file_count=Count('files'))


class TagCreateView(LoginRequiredMixin, CreateView):
    """Create new tag (admin only)"""
    model = FileTag
    form_class = FileTagForm
    template_name = 'register/tag_form.html'
    success_url = reverse_lazy('tag_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Tag created successfully!')
        return super().form_valid(form)


class TagUpdateView(LoginRequiredMixin, UpdateView):
    """Update tag (admin only)"""
    model = FileTag
    form_class = FileTagForm
    template_name = 'register/tag_form.html'
    success_url = reverse_lazy('tag_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Tag updated successfully!')
        return super().form_valid(form)


class TagDeleteView(LoginRequiredMixin, DeleteView):
    """Delete tag (admin only)"""
    model = FileTag
    template_name = 'register/tag_confirm_delete.html'
    success_url = reverse_lazy('tag_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Tag deleted successfully!')
        return super().form_valid(form)


@login_required
def add_tag_to_file(request, uuid):
    """Add a tag to a file"""
    file = get_object_or_404(File, uuid=uuid)
    
    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        tag = get_object_or_404(FileTag, pk=tag_id)
        file.tags.add(tag)
        messages.success(request, f'Tag "{tag.name}" added to file.')
    
    return redirect('file_detail', uuid=uuid)


@login_required
def remove_tag_from_file(request, uuid):
    """Remove a tag from a file"""
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
        
        if not new_file:
            messages.error(request, 'Please upload a document file.')
            return render(request, template_name, {'file': file, 'previous_version': previous_version})
        
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
    
    context = {
        'file': file,
        'previous_version': previous_version,
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
