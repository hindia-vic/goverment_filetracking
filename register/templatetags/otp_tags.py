from django import template
from django_otp.plugins.otp_totp.models import TOTPDevice

register = template.Library()


@register.filter
def has_2fa(user):
    """Check if user has 2FA enabled"""
    if not user.is_authenticated:
        return False
    return TOTPDevice.objects.filter(user=user, confirmed=True).exists()
