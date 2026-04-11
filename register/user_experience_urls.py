from django.urls import path
from . import user_experience_views

urlpatterns = [
    path('file/<uuid:file_uuid>/queue/', user_experience_views.file_queue_position, name='queue_position'),
    path('api/file/<uuid:file_uuid>/queue/', user_experience_views.api_queue_position, name='api_queue_position'),
    path('files/calendar/', user_experience_views.file_calendar_view, name='file_calendar'),
    path('api/files/calendar/', user_experience_views.api_file_calendar, name='api_file_calendar'),
    path('toggle-theme/', user_experience_views.toggle_theme, name='toggle_theme'),
    path('file/<uuid:file_uuid>/workflow/', user_experience_views.file_workflow_status, name='file_workflow'),
    path('api/quick-actions/', user_experience_views.dashboard_quick_actions, name='dashboard_quick_actions'),
]