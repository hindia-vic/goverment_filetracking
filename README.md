# File Tracking System

A comprehensive Django-based File Tracking System for managing physical documents within an organization. This system provides complete file lifecycle management including check-in/check-out, request workflows, QR code generation, notifications, and more.

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

### Security
- **Password Management**: Secure password handling with validation
- **Password Reset**: Email-based password reset functionality
- **Two-Factor Authentication (2FA)**: TOTP-based 2FA for enhanced security
- **Activity Logging**: Complete audit trail of user activities

### Notifications
- **Email Notifications**: Automated email alerts for file status changes
- **In-app Notifications**: Real-time notifications within the application
- **Overdue Alerts**: Automatic notifications for overdue files

### API
- **REST API**: Full-featured REST API using Django REST Framework
- **API Documentation**: Comprehensive API docs available at `/api/docs/`

## Installation

### Prerequisites
- Python 3.8+
- Django 4.0+
- SQLite3 (default) or PostgreSQL/MySQL for production

### Setup

1. **Clone the repository**
   ```bash
   cd your-project-directory
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Open browser at: `http://127.0.0.1:8000`
   - Admin panel at: `http://127.0.0.1:8000/admin`

## Project Structure

```
file_system/
├── file_system/          # Django project settings
│   ├── settings.py       # Main configuration
│   ├── urls.py           # Root URL configuration
│   ├── wsgi.py           # WSGI config
│   └── asgi.py           # ASGI config
├── register/             # Main application
│   ├── models.py         # Database models
│   ├── views.py          # Views and business logic
│   ├── forms.py          # Forms
│   ├── urls.py           # App URL patterns
│   ├── admin.py          # Admin configuration
│   ├── serializers.py    # REST API serializers
│   ├── api.py            # API views
│   ├── emails.py         # Email templates
│   ├── signals.py        # Django signals
│   ├── backends.py       # Custom auth backends
│   └── two_factor_views.py  # 2FA views
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── migrations/           # Database migrations
└── manage.py             # Django management script
```

## User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| Admin | System Administrator | Full access to all features |
| Registry | Registry Officer | Manage files, approve requests, generate reports |
| Department User | Regular User | Request files, view file list |

## API Endpoints

### Authentication
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `POST /api/auth/password-reset/` - Request password reset
- `POST /api/auth/password-reset/confirm/` - Confirm password reset

### Files
- `GET /api/files/` - List files
- `POST /api/files/` - Create file
- `GET /api/files/{uuid}/` - Get file details
- `PUT /api/files/{uuid}/` - Update file
- `DELETE /api/files/{uuid}/` - Delete file

### Departments
- `GET /api/departments/` - List departments
- `POST /api/departments/` - Create department

### Requests
- `GET /api/requests/` - List file requests
- `POST /api/requests/` - Create file request
- `POST /api/requests/{id}/approve/` - Approve request
- `POST /api/requests/{id}/reject/` - Reject request

Full API documentation is available at `/api/docs/` when the server is running.

## Settings Configuration

Key settings in `settings.py`:

```python
# Authentication
AUTHENTICATION_BACKENDS = [
    'register.backends.EmployeeIDBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# File tracking
FILE_OVERDUE_DAYS = 7  # Days before file is considered overdue

# Email (configure for production)
EMAIL_HOST = 'smtp.example.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'noreply@example.com'
```

## Management Commands

### Check Overdue Files
```bash
python manage.py check_overdue
```

### Collect Static Files
```bash
python manage.py collectstatic
```

## Security Best Practices

1. **Change SECRET_KEY**: Update the SECRET_KEY in settings.py for production
2. **DEBUG=False**: Set DEBUG=False in production
3. **ALLOWED_HOSTS**: Configure ALLOWED_HOSTS for your domain
4. **HTTPS**: Use HTTPS in production
5. **Database**: Use PostgreSQL or MySQL for production environments

## Built With

- Django 4.0+ - Web framework
- Django REST Framework - API framework
- Bootstrap 5 - UI framework
- SQLite - Default database (PostgreSQL/MySQL recommended for production)
- django-two-factor-auth - 2FA functionality
- crispy-bootstrap5 - Form rendering

## License

This project is for internal organizational use.

## Support

For issues or questions, contact the system administrator.
