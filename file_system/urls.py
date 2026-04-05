"""
URL configuration for file_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from register.two_factor_views import login_view
import logging

logger = logging.getLogger(__name__)

# Debug logging for media file serving
logger.info(f"DEBUG={settings.DEBUG}")
logger.info(f"MEDIA_URL={settings.MEDIA_URL}")
logger.info(f"MEDIA_ROOT={settings.MEDIA_ROOT}")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', include('register.urls')),
    path('accounts/login/', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

# Serve media files in both DEBUG and production modes
from django.views.static import serve
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}, name='media'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve static files  
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Add re_path for static files as fallback
from django.contrib.staticfiles.views import serve
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}, name='static'),
]
