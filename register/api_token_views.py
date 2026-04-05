"""
Views for API token management
"""
from django.views.generic import ListView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from register.models import APIToken
import secrets


class APITokenListView(LoginRequiredMixin, ListView):
    """List user's API tokens"""
    model = APIToken
    template_name = 'register/api_token_list.html'
    context_object_name = 'tokens'
    paginate_by = 20
    
    def get_queryset(self):
        return APIToken.objects.filter(user=self.request.user)


class APITokenCreateView(LoginRequiredMixin, CreateView):
    """Create a new API token"""
    model = APIToken
    template_name = 'register/api_token_form.html'
    fields = ['name', 'description', 'rate_limit', 'expires_at']
    success_url = reverse_lazy('api_token_list')
    
    def form_valid(self, form):
        token = form.save(commit=False)
        token.user = self.request.user
        token.key = secrets.token_hex(32)
        token.save()
        messages.success(self.request, 'API token created successfully. Save this token now - it cannot be shown again!')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['created_token'] = self.request.session.pop('created_token_key', None)
        return context
    
    def form_invalid(self, form):
        # If valid, store the token in session to display
        if 'name' in form.cleaned_data:
            token = APIToken(user=self.request.user, name=form.cleaned_data['name'])
            token.key = secrets.token_hex(32)
            if form.cleaned_data.get('expires_at'):
                token.expires_at = form.cleaned_data['expires_at']
            token.save()
            self.request.session['created_token_key'] = token.key
            return redirect('api_token_list')
        return super().form_invalid(form)


class APITokenDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an API token"""
    model = APIToken
    template_name = 'register/api_token_confirm_delete.html'
    success_url = reverse_lazy('api_token_list')
    
    def get_queryset(self):
        return APIToken.objects.filter(user=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'API token deleted successfully')
        return super().form_valid(form)


def regenerate_api_token(request, pk):
    """Regenerate a new API token"""
    token = get_object_or_404(APIToken, pk=pk, user=request.user)
    token.key = secrets.token_hex(32)
    token.save()
    messages.success(request, 'New API token generated. Save this token - it cannot be shown again!')
    return redirect('api_token_list')


def toggle_api_token(request, pk):
    """Toggle API token active status"""
    token = get_object_or_404(APIToken, pk=pk, user=request.user)
    token.is_active = not token.is_active
    token.save()
    status = 'activated' if token.is_active else 'deactivated'
    messages.success(request, f'API token {status}')
    return redirect('api_token_list')