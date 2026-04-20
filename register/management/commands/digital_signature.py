"""
Django management command to manage digital signatures
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from register.models import DigitalSignature
import hashlib
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Manage digital signatures for users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create digital signature for a user'
        )
        parser.add_argument(
            '--revoke',
            action='store_true',
            help='Revoke digital signature for a user'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all digital signatures'
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify digital signature for a user'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the operation'
        )
    
    def handle(self, *args, **options):
        if options['create']:
            self.create_signature(options['username'])
        elif options['revoke']:
            self.revoke_signature(options['username'])
        elif options['list']:
            self.list_signatures()
        elif options['verify']:
            self.verify_signature(options['username'])
        else:
            self.stdout.write(self.style.WARNING('No option specified. Use --help for options.'))
    
    def create_signature(self, username):
        """Create a digital signature for a user"""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {username} not found'))
            return
        
        # Check if signature already exists
        if hasattr(user, 'digital_signature'):
            self.stdout.write(self.style.WARNING(f'Digital signature already exists for {username}'))
            return
        
        # Generate key pair
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import base64
        
        # Generate key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Generate fingerprint
        fingerprint = hashlib.sha256(public_pem).hexdigest()
        
        # Generate serial and salt
        serial = hashlib.sha256(f"{user.username}:{fingerprint}".encode()).hexdigest()[:16]
        salt = os.urandom(16).hex()
        
        # Create signature record
        sig = DigitalSignature.objects.create(
            user=user,
            public_key=public_pem.decode(),
            private_key_encrypted=base64.b64encode(private_pem).decode(),
            key_fingerprint=fingerprint,
            certificate_serial=serial,
            salt=salt
        )
        
        self.stdout.write(self.style.SUCCESS(f'Created digital signature for {username}'))
        self.stdout.write(f'  Fingerprint: {fingerprint}'[:32])
        self.stdout.write(f'  Serial: {serial}'[:16])
        self.stdout.write(f'  Valid until: {sig.certificate_not_after.date()}')
    
    def revoke_signature(self, username):
        """Revoke a digital signature"""
        try:
            sig = DigitalSignature.objects.get(user__username=username)
        except DigitalSignature.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No digital signature for {username}'))
            return
        
        sig.is_revoked = True
        sig.save()
        
        self.stdout.write(self.style.SUCCESS(f'Revoked digital signature for {username}'))
    
    def list_signatures(self):
        """List all digital signatures"""
        sigs = DigitalSignature.objects.select_related('user')
        
        self.stdout.write('\nDigital Signatures:\n')
        for sig in sigs:
            status = 'VALID' if sig.is_valid() else 'INVALID/REVOKED'
            self.stdout.write(f'  {sig.user.username}: {status} (valid until {sig.certificate_not_after.date()})')
        
        self.stdout.write(f'\nTotal: {len(sigs)} signatures')
    
    def verify_signature(self, username):
        """Verify digital signature functionality"""
        try:
            sig = DigitalSignature.objects.get(user__username=username)
        except DigitalSignature.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No digital signature for {username}'))
            return
        
        # Test signing
        test_data = "Test signature data"
        
        try:
            signature = sig.sign(test_data)
            self.stdout.write(f'  Signing: OK')
            
            # Test verification
            result = sig.verify(test_data, signature)
            self.stdout.write(f'  Verification: {"OK" if result else "FAILED"}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))