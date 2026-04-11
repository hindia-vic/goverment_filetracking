from django.urls import path
from . import security_views

urlpatterns = [
    path('login-history/', security_views.login_history, name='login_history'),
    path('sessions/', security_views.active_sessions, name='active_sessions'),
    path('sessions/<int:session_id>/terminate/', security_views.terminate_session, name='terminate_session'),
    path('sessions/terminate-all/', security_views.terminate_all_sessions, name='terminate_all_sessions'),
    path('access-logs/', security_views.access_logs, name='access_logs'),
    path('dashboard/', security_views.security_dashboard, name='security_dashboard'),
]