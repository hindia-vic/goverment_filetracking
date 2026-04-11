from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta

from register.models import LoginAttempt, UserSession, AccessLog
from .security_forms import SessionManagementForm, AccessLogFilterForm


@login_required
def login_history(request):
    """View login history for current user"""
    attempts = LoginAttempt.objects.filter(username=request.user.username)
    
    # Summary stats
    total_logins = attempts.filter(status='success').count()
    failed_attempts = attempts.filter(status='failed').count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_attempts = attempts.filter(timestamp__gte=thirty_days_ago)
    
    # Group by date
    login_dates = {}
    for attempt in recent_attempts:
        date_key = attempt.timestamp.strftime('%Y-%m-%d')
        if date_key not in login_dates:
            login_dates[date_key] = {'success': 0, 'failed': 0}
        if attempt.status == 'success':
            login_dates[date_key]['success'] += 1
        else:
            login_dates[date_key]['failed'] += 1
    
    context = {
        'attempts': attempts[:50],
        'total_logins': total_logins,
        'failed_attempts': failed_attempts,
        'login_dates': login_dates,
    }
    return render(request, 'register/security/login_history.html', context)


@login_required
def active_sessions(request):
    """View and manage active sessions"""
    sessions = UserSession.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-last_activity')
    
    # Current session
    current_session_key = request.session.session_key
    current_session = sessions.filter(session_key=current_session_key).first()
    
    if request.method == 'POST':
        form = SessionManagementForm(request.user, request.POST)
        if form.is_valid():
            count = form.save()
            messages.success(request, f'{count} session(s) terminated.')
            return redirect('active_sessions')
    else:
        form = SessionManagementForm(request.user)
    
    context = {
        'sessions': sessions,
        'current_session': current_session,
        'form': form,
    }
    return render(request, 'register/security/active_sessions.html', context)


@login_required
def access_logs(request):
    """View access logs with filtering"""
    logs = AccessLog.objects.select_related('user', 'file').order_by('-timestamp')[:200]
    
    if request.GET:
        form = AccessLogFilterForm(request.GET)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            action = form.cleaned_data.get('action')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            ip_address = form.cleaned_data.get('ip_address')
            
            if user:
                logs = logs.filter(user=user)
            if action:
                logs = logs.filter(action=action)
            if start_date:
                logs = logs.filter(timestamp__date__gte=start_date)
            if end_date:
                logs = logs.filter(timestamp__date__lte=end_date)
            if ip_address:
                logs = logs.filter(ip_address=ip_address)
    else:
        form = AccessLogFilterForm()
    
    context = {
        'logs': logs[:100],
        'form': form,
    }
    return render(request, 'register/security/access_logs.html', context)


@login_required
def security_dashboard(request):
    """Security dashboard for admin"""
    from django.contrib.auth.models import User
    
    # Permission check
    if not request.user.is_superuser and not getattr(request.user, 'profile', None):
        from register.models import UserProfile
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role not in ['admin', 'registry']:
            from django.http import Http403Forbidden
            return render(request, '403.html', status=403)
    
    now = timezone.now()
    today = now.date()
    thirty_days_ago = now - timedelta(days=30)
    
    # Login attempts stats
    total_attempts = LoginAttempt.objects.count()
    today_attempts = LoginAttempt.objects.filter(timestamp__date=today)
    failed_today = today_attempts.filter(status='failed').count()
    success_today = today_attempts.filter(status='success').count()
    
    # Recent failed attempts (potential threats)
    recent_failed = LoginAttempt.objects.filter(
        status='failed',
        timestamp__gte=thirty_days_ago
    ).values('username').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # IP analysis
    suspicious_ips = LoginAttempt.objects.filter(
        status='failed',
        timestamp__gte=thirty_days_ago
    ).values('ip_address').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Active sessions
    active_sessions_count = UserSession.objects.filter(is_active=True).count()
    
    # User access summary
    active_users = AccessLog.objects.filter(
        timestamp__gte=thirty_days_ago
    ).values('user__username').annotate(
        access_count=Count('id')
    ).order_by('-access_count')[:10]
    
    # Action breakdown
    action_stats = AccessLog.objects.filter(
        timestamp__gte=thirty_days_ago
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'total_attempts': total_attempts,
        'failed_today': failed_today,
        'success_today': success_today,
        'recent_failed': recent_failed,
        'suspicious_ips': suspicious_ips,
        'active_sessions_count': active_sessions_count,
        'active_users': active_users,
        'action_stats': action_stats,
    }
    return render(request, 'register/security/security_dashboard.html', context)


@login_required
def terminate_session(request, session_id):
    """Terminate a specific session"""
    session = get_object_or_404(
        UserSession,
        id=session_id,
        user=request.user,
        is_active=True
    )
    
    # Don't allow terminating current session through this view
    if session.session_key == request.session.session_key:
        messages.error(request, 'Cannot terminate your current session.')
        return redirect('active_sessions')
    
    session.is_active = False
    session.save()
    messages.success(request, 'Session terminated.')
    return redirect('active_sessions')


@login_required
def terminate_all_sessions(request):
    """Terminate all sessions except current"""
    sessions = UserSession.objects.filter(
        user=request.user,
        is_active=True
    ).exclude(session_key=request.session.session_key)
    
    count = sessions.count()
    sessions.update(is_active=False)
    
    messages.success(request, f'{count} session(s) terminated.')
    return redirect('active_sessions')