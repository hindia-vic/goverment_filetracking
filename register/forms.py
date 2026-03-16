from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, HTML
from .models import File, FileMovement, Department, UserProfile, FileRequest, FileTag


class UserRegistrationForm(UserCreationForm):
    """Form for user self-registration"""
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    employee_id = forms.CharField(max_length=50, required=True, label="Employee ID")
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        empty_label="Select Department",
        required=True,
        label="Your Department"
    )
    phone = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'employee_id', 'department', 'phone', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
            ),
            'username',
            'email',
            Row(
                Column('employee_id', css_class='col-md-6'),
                Column('department', css_class='col-md-6'),
            ),
            'phone',
            Row(
                Column('password1', css_class='col-md-6'),
                Column('password2', css_class='col-md-6'),
            ),
            Submit('submit', 'Register', css_class='btn btn-primary w-100 mt-3')
        )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already in use
            if User.objects.filter(email__iexact=email).exists():
                raise forms.ValidationError('This email has already been used. Please use a different email address.')
        return email
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            # Check if employee_id is already in use
            if UserProfile.objects.filter(employee_id__iexact=employee_id).exists():
                raise forms.ValidationError('This employee ID has already been registered. Please use a different employee ID.')
        return employee_id
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Create/update profile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'employee_id': self.cleaned_data['employee_id'],
                    'department': self.cleaned_data['department'],
                    'phone': self.cleaned_data.get('phone', ''),
                    'role': 'department_user'  # Default role
                }
            )
        return user


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile (admin or self)"""
    class Meta:
        model = UserProfile
        fields = ['role', 'department', 'employee_id', 'phone', 'is_active']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Check if user is admin
        self.admin_user = kwargs.pop('admin_user', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        
        # If not admin, remove role field (only admin can change roles)
        if not self.admin_user or not (self.admin_user.is_superuser or getattr(self.admin_user, 'profile', None) and self.admin_user.profile.role in ['admin']):
            # Regular user form - remove sensitive fields
            self.fields.pop('role', None)
            self.fields.pop('is_active', None)
            self.helper.layout = Layout(
                Row(
                    Column('employee_id', css_class='col-md-6'),
                    Column('phone', css_class='col-md-6'),
                ),
                'department',
                Submit('submit', 'Update Profile', css_class='btn btn-primary')
            )
        else:
            # Admin form - include all fields
            self.helper.layout = Layout(
                Row(
                    Column('employee_id', css_class='col-md-6'),
                    Column('role', css_class='col-md-6'),
                ),
                'department',
                'phone',
                'is_active',
                Submit('submit', 'Update Profile', css_class='btn btn-primary')
            )


class DepartmentForm(forms.ModelForm):
    """Form for creating/editing departments (admin only)"""
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('code', css_class='col-md-6'),
            ),
            'description',
            'is_active',
            Submit('submit', 'Save Department', css_class='btn btn-primary')
        )


class FileUploadForm(forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = File
        fields = ['department', 'title', 'description', 'priority', 'file_attachment']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'file_attachment': forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('department', css_class='form-group col-md-6 mb-0'),
                Column('priority', css_class='form-group col-md-6 mb-0'),
            ),
            'title',
            'description',
            'file_attachment',
            Submit('submit', 'Create File & Generate QR Code', css_class='btn btn-primary')
        )
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.created_by = self.user
            instance.original_filename = instance.file_attachment.name if instance.file_attachment else ''
        if commit:
            instance.save()
            # Create initial version if file attached
            if instance.file_attachment:
                instance.create_version(
                    user=self.user,
                    change_type='create',
                    notes='Initial version',
                    file_attachment=instance.file_attachment
                )
        return instance


class FileRequestForm(forms.ModelForm):
    """Form for requesting file checkout"""
    class Meta:
        model = FileRequest
        fields = ['purpose']
        widgets = {
            'purpose': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter purpose for requesting this file...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'purpose',
            Submit('submit', 'Request File', css_class='btn btn-warning w-100')
        )


class FileRequestApprovalForm(forms.Form):
    """Form for registry to approve/reject file request"""
    ACTION_CHOICES = [
        ('approve', 'Approve & Set Pickup Date'),
        ('reject', 'Reject Request'),
    ]
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.RadioSelect)
    pickup_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Pickup Date (for approval)"
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Notes/Reason"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'action',
            'pickup_date',
            'notes',
            Submit('submit', 'Submit', css_class='btn btn-primary')
        )


class FileHandoverForm(forms.Form):
    """Form for registry to confirm file has been handed to user"""
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Handover Notes"
    )
    confirmation_code = forms.CharField(
        max_length=50,
        label="User Confirmation Code",
        help_text="Enter user's employee ID to confirm handover"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'notes',
            'confirmation_code',
            Submit('submit', 'Confirm Handover', css_class='btn btn-success w-100')
        )


class UserConfirmationForm(forms.Form):
    """Form for user to confirm receipt of file"""
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label="Confirmation Notes"
    )
    confirmation_code = forms.CharField(
        max_length=50,
        label="Your Confirmation Code",
        help_text="Enter your employee ID to confirm receipt"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'notes',
            'confirmation_code',
            Submit('submit', 'Confirm Receipt', css_class='btn btn-success w-100')
        )


class CheckoutForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Receiving Department"
    )
    recipient_name = forms.CharField(max_length=100, label="Officer Name")
    recipient_designation = forms.CharField(max_length=100, label="Designation")
    purpose = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    signature_confirmation = forms.CharField(
        max_length=50,
        label="Confirmation Code",
        help_text="Enter your employee ID as digital signature"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'department',
            Row(
                Column('recipient_name', css_class='col-md-6'),
                Column('recipient_designation', css_class='col-md-6'),
            ),
            'purpose',
            Field('signature_confirmation', css_class='text-uppercase'),
            Submit('submit', 'Confirm Checkout & Sign', css_class='btn btn-warning')
        )


class CheckinForm(forms.Form):
    condition = forms.ChoiceField(choices=[
        ('good', 'Good - No Damage'),
        ('damaged', 'Damaged'),
        ('incomplete', 'Incomplete Pages'),
    ])
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    signature_confirmation = forms.CharField(
        max_length=50,
        label="Confirmation Code",
        help_text="Enter your employee ID to confirm return"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'condition',
            'notes',
            Field('signature_confirmation', css_class='text-uppercase'),
            Submit('submit', 'Confirm Return to Registry', css_class='btn btn-success')
        )


class AuditFilterForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="All Departments"
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    status = forms.ChoiceField(
        choices=[('', 'All')] + File.STATUS_CHOICES,
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('department', css_class='col-md-4'),
                Column('status', css_class='col-md-4'),
            ),
            Row(
                Column('date_from', css_class='col-md-3'),
                Column('date_to', css_class='col-md-3'),
            ),
            Submit('submit', 'Filter Records', css_class='btn btn-info')
        )


class FileTagForm(forms.ModelForm):
    """Form for creating/editing file tags"""
    class Meta:
        model = FileTag
        fields = ['name', 'color', 'description']
        widgets = {
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control-color'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='col-md-6'),
                Column('color', css_class='col-md-6'),
            ),
            'description',
            Submit('submit', 'Save Tag', css_class='btn btn-primary')
        )
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Check if tag name already exists
            existing = FileTag.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError('A tag with this name already exists.')
        return name