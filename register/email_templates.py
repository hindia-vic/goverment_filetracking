"""
Email templates for File Tracking System
"""
from django.conf import settings


EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            background: #f8f9fa;
            padding: 30px;
            border: 1px solid #e9ecef;
            border-top: none;
            border-radius: 0 0 10px 10px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card-header {{
            font-weight: bold;
            color: #0d6efd;
            margin-bottom: 10px;
            font-size: 14px;
            text-transform: uppercase;
        }}
        .label {{
            color: #6c757d;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .value {{
            color: #212529;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            background: #0d6efd;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            margin: 10px 5px;
        }}
        .btn:hover {{
            background: #0a58ca;
        }}
        .btn-secondary {{
            background: #6c757d;
        }}
        .btn-secondary:hover {{
            background: #5a6268;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            font-size: 12px;
        }}
        .status-approved {{
            color: #198754;
            font-weight: bold;
        }}
        .status-rejected {{
            color: #dc3545;
            font-weight: bold;
        }}
        .status-pending {{
            color: #ffc107;
            font-weight: bold;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-primary {{ background: #0d6efd; color: white; }}
        .badge-success {{ background: #198754; color: white; }}
        .badge-warning {{ background: #ffc107; color: #000; }}
        .badge-danger {{ background: #dc3545; color: white; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📁 {{ site_name }}</h1>
    </div>
    <div class="content">
        {{ content|safe }}
    </div>
    <div class="footer">
        <p>This is an automated message from {{ site_name }}</p>
        <p>© 2026 {{ site_name }}. All rights reserved.</p>
    </div>
</body>
</html>
"""


def get_email_context(site_name="File Tracking System"):
    """Common email context"""
    return {
        'site_name': site_name,
        'base_url': getattr(settings, 'BASE_URL', 'http://localhost:8000'),
    }


def render_email(content, subject, site_name="File Tracking System"):
    """Render HTML email with template"""
    context = {
        'subject': subject,
        'content': content,
        'site_name': site_name,
    }
    return EMAIL_TEMPLATE.format(**{k: str(v) for k, v in context.items()})