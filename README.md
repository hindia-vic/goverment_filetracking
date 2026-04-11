# File Tracking System

A comprehensive Django-based File Tracking System for managing physical documents within an organization. This system provides complete file lifecycle management including check-in/check-out, request workflows, QR code generation, notifications, and enterprise-grade features.

## Features

### Core Functionality
- **File Management**: Upload, track, and manage physical files with unique reference numbers
- **QR Code Generation**: Auto-generated QR codes for each file for easy scanning
- **Check-in/Check-out**: Track file movements between users and departments
- **Request Workflow**: Users can request files and administrators can approve/reject requests
- **Due Date Tracking**: Automatic overdue alerts and notifications
- **File Archives**: Archive files with reasons and restore them when needed
- **File Versions**: Track changes and maintain version history for files
- **File Tags & Categories**: Organize files with custom tags

### User Management
- **Role-based Access**: Support for Admin, Registry Officer, and Department User roles
- **User Profiles**: Extended user profiles with department and employee ID
- **Authentication**: Email/password-based authentication with session management
- **Two-Factor Authentication (2FA)**: TOTP-based 2FA for enhanced security

### Security & Compliance
- **Login Attempt Tracking**: Track successful/failed login attempts with IP logging
- **Account Lockout**: Automatic lockout after 5 failed attempts
- **IP-based Lockout**: Block IPs with excessive failed attempts
- **Session Management**: View and terminate active sessions
- **Access Logging**: Comprehensive audit trail of all user actions
- **Security Dashboard**: Admin overview of security metrics

### Notifications & Communication
- **Email Notifications**: Automated HTML email alerts for file status changes
- **In-app Notifications**: Real-time notifications within the application
- **Overdue Alerts**: Automatic notifications for overdue files
- **Notification Preferences**: Users can customize their notification settings
- **Email Digests**: Scheduled email reports

### User Experience
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Mobile-friendly interface
- **Global Search**: Search files with autocomplete
- **File Calendar**: Visual calendar showing file availability
- **Queue Position**: Users can see their position in file request queue
- **Activity Timeline**: Visual timeline of all file activities
- **Breadcrumb Navigation**: Easy page hierarchy

### Data & Reporting
- **Export to CSV**: Export files and requests to CSV format
- **Export to PDF**: Generate PDF reports
- **Export to Excel**: Export to Excel (.xlsx) format with formatting
- **Advanced Filtering**: Filter by status, department, date range, holder
- **Audit Reports**: Comprehensive audit trail reports
- **Dashboard Analytics**: Charts and statistics

### API
- **REST API**: Full-featured REST API using Django REST Framework
- **API Key Authentication**: Generate and manage API tokens for external integrations
- **Rate Limiting**: API rate limiting for security

### Integration
- **Webhooks**: Configure webhooks for external integrations
- **Document Preview**: Preview PDF and image files inline

## Installation

### Prerequisites
- Python 3.8+
- Django 6.0+
- PostgreSQL/MySQL (recommended for production)

### Setup

1. **Clone and setup virtual environment**
   ```bash
   cd file_system
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Copy `.env.example` to `.env` and configure settings
   - Or update `settings.py` directly

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Open browser at: `http://127.0.0.1:8000`
   - Admin panel at: `http://127.0.0.1:8000/admin`

## User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| Admin | System Administrator | Full access to all features |
| Registry | Registry Officer | Manage files, approve requests, generate reports |
| Department User | Regular User | Request files, view file list |

## Key URLs

- **Dashboard**: `/register/`
- **File List**: `/register/files/`
- **Calendar**: `/register/calendar/`
- **Activity Timeline**: `/register/activity-timeline/`
- **Export Center**: `/register/export/`
- **Security Dashboard**: `/register/security/dashboard/`
- **Login History**: `/register/security/login-history/`
- **Active Sessions**: `/register/security/sessions/`
- **Account Settings**: `/register/account/`
- **2FA Setup**: `/register/2fa/setup/`

## Management Commands

```bash
# Check overdue files
python manage.py check_overdue

# System health check
python manage.py system_health

# Send reminder emails
python manage.py send_reminders

# Audit retention cleanup
python manage.py audit_retention

# Import files from CSV
python manage.py import_files

# Scheduled reports
python manage.py scheduled_reports
```

## Settings Configuration

Key settings in `settings.py`:

```python
# Authentication
AUTHENTICATION_BACKENDS = [
    'register.backends.EmployeeIDBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Security
LOGIN_LOCKOUT_THRESHOLD = 5  # Failed attempts before lockout
LOGIN_LOCKOUT_DURATION = 30  # Lockout duration in minutes
IP_LOCKOUT_THRESHOLD = 10

# File tracking
FILE_OVERDUE_DAYS = 7
```

## Technology Stack

- **Django 6.0** - Web framework
- **Django REST Framework** - API framework
- **Bootstrap 5** - UI framework
- **PostgreSQL** - Database (recommended)
- **WhiteNoise** - Static file serving
- **ReportLab** - PDF generation
- **OpenPyXL** - Excel export
- **django-two-factor-auth** - 2FA functionality

## Security Best Practices

1. **Change SECRET_KEY**: Update the SECRET_KEY in settings.py for production
2. **DEBUG=False**: Set DEBUG=False in production
3. **ALLOWED_HOSTS**: Configure ALLOWED_HOSTS for your domain
4. **HTTPS**: Use HTTPS in production
5. **Database**: Use PostgreSQL or MySQL for production environments
6. **Environment Variables**: Use environment variables for sensitive data

## Project Structure

```
file_system/
├── file_system/          # Django project settings
│   ├── settings.py       # Main configuration
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py           # WSGI config
├── register/             # Main application
│   ├── models.py         # Database models
│   ├── views.py          # Views and business logic
│   ├── urls.py           # App URL patterns
│   ├── api.py            # REST API views
│   ├── advanced_features.py  # Export, bulk operations
│   ├── calendar_views.py     # File calendar
│   ├── security_views.py    # Security dashboard
│   ├── user_experience_views.py  # UX features
│   └── two_factor_views.py  # 2FA views
├── templates/            # HTML templates
├── static/               # CSS, JS, images
└── manage.py             # Django management script
```

## License

This project is for internal organizational use.

## Support

For issues or questions, contact the system administrator.
