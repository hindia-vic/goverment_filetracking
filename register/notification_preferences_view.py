"""
View for notification preferences
"""
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from register.models import NotificationPreferences


class NotificationPreferencesView(LoginRequiredMixin, UpdateView):
    """User notification preferences"""
    model = NotificationPreferences
    template_name = 'register/notification_preferences.html'
    fields = [
        'email_request_approved', 'email_request_rejected', 
        'email_file_due', 'email_file_overdue',
        'email_return_verified', 'email_return_rejected',
        'email_new_request', 'email_weekly_summary',
        'in_app_notifications', 'digest_frequency'
    ]
    success_url = reverse_lazy('notification_preferences')
    
    def get_object(self):
        prefs, created = NotificationPreferences.objects.get_or_create(user=self.request.user)
        return prefs
    
    def form_valid(self, form):
        messages.success(self.request, 'Notification preferences saved successfully!')
        return super().form_valid(form)