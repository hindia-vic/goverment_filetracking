import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'file_system.settings')

# Import settings first
from django.conf import settings

# Patch DRF to not register converter
try:
    from rest_framework.parsers import BaseParser
    from rest_framework.relations import RouterVariable
    from django.urls import convertors
    
    # Check if already registered
    if 'drf_format_suffix' in converters.TypeConverterConverter._converters:
        pass  # Already registered
    else:
        from django.urls.converters import register_converter
        register_converter(RouterVariable, 'drf_format_suffix')
except Exception:
    pass

django.setup()