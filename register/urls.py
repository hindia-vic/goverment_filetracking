from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from . import views
from .api import (
    DepartmentViewSet, FileViewSet, FileMovementViewSet,
    FileRequestViewSet, NotificationViewSet, ActivityLogViewSet,
    UserProfileViewSet, api_status, dashboard_stats
)
from .two_factor_views import (
    setup_2fa, disable_2fa, verify_2fa, 
    view_backup_codes, regenerate_backup_codes,
    login_view, verify_2fa_login
)

# Create router for API viewsets
router = DefaultRouter()
router.register(r'departments', DepartmentViewSet)
router.register(r'files', FileViewSet)
router.register(r'movements', FileMovementViewSet)
router.register(r'requests', FileRequestViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'activity', ActivityLogViewSet)
router.register(r'profiles', UserProfileViewSet)

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    path('api/status/', api_status, name='api_status'),
    path('api/dashboard/', dashboard_stats, name='api_dashboard_stats'),
    
    # Two-Factor Authentication
    path('2fa/setup/', setup_2fa, name='setup_2fa'),
    path('2fa/disable/', disable_2fa, name='disable_2fa'),
    path('2fa/verify/', verify_2fa, name='verify_2fa'),
    path('2fa/backup-codes/', view_backup_codes, name='view_backup_codes'),
    path('2fa/regenerate-codes/', regenerate_backup_codes, name='regenerate_backup_codes'),
    
    # Login with 2FA
    path('login/verify/', verify_2fa_login, name='verify_2fa_login'),
    
    # Dashboard and file views
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('files/', views.FileListView.as_view(), name='file_list'),
    path('files/upload/', views.FileCreateView.as_view(), name='file_upload'),
    path('files/<uuid:uuid>/', views.FileDetailView.as_view(), name='file_detail'),
    path('files/<uuid:uuid>/checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('files/<uuid:uuid>/checkin/', views.CheckinView.as_view(), name='checkin'),
    path('files/<uuid:uuid>/qr/', views.QRCodeView.as_view(), name='qr_code'),
    
    # File request workflow
    path('files/<uuid:uuid>/request/', views.FileRequestCreateView.as_view(), name='file_request'),
    path('requests/', views.FileRequestListView.as_view(), name='request_list'),
    path('requests/<int:pk>/process/', views.FileRequestProcessView.as_view(), name='request_process'),
    path('requests/<int:pk>/handover/', views.FileRequestHandoverView.as_view(), name='request_handover'),
    path('requests/<int:pk>/confirm/', views.FileRequestConfirmView.as_view(), name='request_confirm'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    
    # Admin: Departments
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<int:pk>/edit/', views.DepartmentUpdateView.as_view(), name='department_edit'),
    
    # Admin: Users
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    
    # Reports
    path('overdue/', views.OverdueListView.as_view(), name='overdue_list'),
    path('audit/', views.AuditReportView.as_view(), name='audit_report'),
    path('activity/', views.ActivityLogListView.as_view(), name='activity_log'),
    
    # File versioning and archives
    path('files/<uuid:uuid>/archive/', views.FileArchiveView.as_view(), name='file_archive'),
    path('files/<uuid:uuid>/restore/', views.FileRestoreView.as_view(), name='file_restore'),
    path('files/<uuid:uuid>/versions/', views.FileVersionHistoryView.as_view(), name='file_versions'),
    
    # User registration
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Account settings and security
    path('account/', views.AccountSettingsView.as_view(), name='account_settings'),
    path('account/password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Password reset - using custom views
    path('password/reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        email_template_name='registration/password_reset_email.html',
        success_url='/register/password/reset/done/',
        from_email='victorhindia@gmail.com'
    ), name='password_reset'),
    path('password/reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/register/password/reset/complete/'
        ), 
         name='password_reset_confirm'),
    path('password/reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ), 
         name='password_reset_complete'),
]