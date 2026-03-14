from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django_otp.plugins.otp_totp.models import TOTPDevice
import io
import base64
import pyotp
import secrets
import base64


def login_view(request):
    """Custom login view that checks for 2FA"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Use Django's authentication to verify username/password
        from django.contrib.auth import authenticate, login
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user has 2FA enabled
            has_2fa = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
            
            if has_2fa:
                # Store user in session and redirect to 2FA verification
                login(request, user)
                request.session['2fa_required'] = True
                return redirect('verify_2fa_login')
            else:
                # No 2FA, proceed with normal login
                login(request, user)
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'registration/login.html')


def verify_2fa_login(request):
    """Verify 2FA during login"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        
        if not token:
            messages.error(request, 'Please enter the verification code.')
            return redirect('verify_2fa_login')
        
        # Get user's 2FA device
        devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
        
        if not devices.exists():
            # No 2FA device, proceed
            return redirect('dashboard')
        
        device = devices.first()
        
        # Verify using pyotp
        totp = pyotp.TOTP(device.key)
        
        if totp.verify(token, valid_window=1):
            # Mark session as verified
            request.session['otp_verified'] = True
            messages.success(request, 'Login successful!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    return render(request, 'registration/2fa_verify.html', {
        'is_login': True
    })


@login_required
def setup_2fa(request):
    """Setup TOTP-based 2FA for the user"""
    # Delete any existing devices for this user
    TOTPDevice.objects.filter(user=request.user, name='default').delete()
    
    if request.method == 'POST':
        # Get the secret from the form
        secret = request.POST.get('secret', '').strip()
        token = request.POST.get('token', '').strip()
        
        if not secret or not token:
            messages.error(request, 'Missing verification details. Please try again.')
            return redirect('setup_2fa')
        
        try:
            # Use pyotp to verify the token directly
            totp = pyotp.TOTP(secret)
            
            # Check if the token is valid (allows for 1 step tolerance)
            if not totp.verify(token, valid_window=1):
                messages.error(request, 'Invalid verification code. Please make sure your device time is correct and try again.')
                return redirect('setup_2fa')
            
            # Token is valid, create the confirmed device
            device = TOTPDevice.objects.create(
                user=request.user,
                name='default',
                key=secret,  # This should be Base32 encoded
                confirmed=True
            )
            
            messages.success(request, 'Two-factor authentication has been enabled successfully!')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}. Please try again.')
            return redirect('setup_2fa')
    
    # Generate a new secret - use Base32 encoding (standard for TOTP)
    secret_bytes = secrets.token_bytes(20)  # 20 bytes = 160 bits
    secret = base64.b32encode(secret_bytes).decode('utf-8').replace('=', '')
    
    issuer = 'FileTrackingSystem'
    account = request.user.email or request.user.username
    
    # Generate otpauth URL using pyotp
    qr_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account,
        issuer_name=issuer
    )
    
    # Generate QR code as base64 image
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    context = {
        'secret': secret,
        'qr_code': qr_base64,
        'qr_url': qr_url,
    }
    
    return render(request, 'registration/2fa_setup.html', context)


@login_required
def disable_2fa(request):
    """Disable 2FA for the user"""
    if request.method == 'POST':
        # Get confirmation
        confirm = request.POST.get('confirm', '')
        
        if confirm.lower() == 'disable':
            # Delete all TOTP devices for the user
            TOTPDevice.objects.filter(user=request.user).delete()
            messages.success(request, 'Two-factor authentication has been disabled.')
        else:
            messages.error(request, 'Please type "disable" to confirm.')
        
        return redirect('account_settings')
    
    return render(request, 'registration/2fa_disable.html')


@login_required
def verify_2fa(request):
    """Verify 2FA token during login"""
    # Check if user has 2FA enabled
    devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
    
    if not devices.exists():
        # User doesn't have 2FA, redirect to setup
        return redirect('setup_2fa')
    
    device = devices.first()
    
    if request.method == 'POST':
        token = request.POST.get('token', '')
        
        if device.verify_token(token):
            # Mark device as verified for this session
            request.session['otp_verified'] = True
            request.session['otp_device_id'] = device.id
            
            messages.success(request, 'Verification successful!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')
    
    return render(request, 'registration/2fa_verify.html')


@login_required
def view_backup_codes(request):
    """View backup codes for 2FA"""
    from django.contrib.auth.hashers import make_password
    import random
    import string
    
    # Generate backup codes
    backup_codes = []
    for _ in range(10):
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        backup_codes.append(code)
    
    # Store hashed codes in session (in production, store in database)
    hashed_codes = [make_password(code) for code in backup_codes]
    request.session['backup_codes'] = hashed_codes
    request.session['backup_codes_generated'] = True
    
    context = {
        'backup_codes': backup_codes,
    }
    
    return render(request, 'registration/2fa_backup_codes.html', context)


@login_required
def regenerate_backup_codes(request):
    """Regenerate backup codes for 2FA"""
    if request.method == 'POST':
        return redirect('view_backup_codes')
    
    return render(request, 'registration/2fa_regenerate_codes.html')
