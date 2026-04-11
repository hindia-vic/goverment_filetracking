from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.sites.models import Site
from django.template.loader import render_to_string


class HTMLPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        """
        Send a django.core.mail.EmailEmail to the given email address.
        """
        from django.core.mail import EmailMultiAlternatives
        from django.utils.html import strip_tags
        
        # Get site domain
        try:
            site = Site.objects.get_current()
            domain = site.domain
            name = site.name
        except:
            domain = 'localhost:8000'
            name = 'File Tracking System'
        
        context['domain'] = domain
        context['site_name'] = name
        
        # Subject
        subject = 'Password Reset - File Tracking System'
        
        # Render HTML email using our custom template
        html_content = render_to_string('registration/password_reset_email.html', context)
        
        # Create plain text version
        text_content = strip_tags(html_content)
        
        # Create email with both HTML and plain text
        email = EmailMultiAlternatives(
            subject,
            text_content,
            from_email,
            [to_email]
        )
        email.attach_alternative(html_content, 'text/html')
        email.send()