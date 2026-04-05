"""
Views for webhook management
"""
from django.views.generic import ListView, CreateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from register.models import Webhook, WebhookDelivery


class WebhookListView(LoginRequiredMixin, ListView):
    """List all webhooks - Admin only"""
    model = Webhook
    template_name = 'register/webhook_list.html'
    context_object_name = 'webhooks'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )):
            messages.error(request, 'Permission denied')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['event_types'] = Webhook.EVENT_TYPES
        return context


class WebhookCreateView(LoginRequiredMixin, CreateView):
    """Create a new webhook"""
    model = Webhook
    template_name = 'register/webhook_form.html'
    fields = ['name', 'url', 'secret', 'event_types', 'is_active']
    success_url = reverse_lazy('webhook_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )):
            messages.error(request, 'Permission denied')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Webhook created successfully')
        return super().form_valid(form)


class WebhookDetailView(LoginRequiredMixin, DetailView):
    """View webhook details and delivery history"""
    model = Webhook
    template_name = 'register/webhook_detail.html'
    context_object_name = 'webhook'
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )):
            messages.error(request, 'Permission denied')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deliveries'] = self.object.deliveries.all()[:20]
        return context


class WebhookDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a webhook"""
    model = Webhook
    template_name = 'register/webhook_confirm_delete.html'
    success_url = reverse_lazy('webhook_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or (
            hasattr(request.user, 'profile') and 
            request.user.profile.role in ['registry', 'admin']
        )):
            messages.error(request, 'Permission denied')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        messages.success(self.request, 'Webhook deleted successfully')
        return super().form_valid(form)


def test_webhook(request, pk):
    """Test a webhook by sending a test event"""
    webhook = get_object_or_404(Webhook, pk=pk)
    
    from register.webhook_service import WebhookService
    
    test_data = {
        'test': True,
        'message': 'This is a test webhook from File Tracking System',
        'timestamp': timezone.now().isoformat()
    }
    
    success = WebhookService.send_webhook(webhook, 'test', test_data)
    
    if success:
        messages.success(request, f'Test webhook sent successfully to {webhook.url}')
    else:
        messages.error(request, f'Failed to send test webhook to {webhook.url}')
    
    return redirect('webhook_detail', pk=pk)


def toggle_webhook(request, pk):
    """Toggle webhook active status"""
    webhook = get_object_or_404(Webhook, pk=pk)
    webhook.is_active = not webhook.is_active
    webhook.save()
    
    status = 'activated' if webhook.is_active else 'deactivated'
    messages.success(request, f'Webhook {status}')
    
    return redirect('webhook_list')