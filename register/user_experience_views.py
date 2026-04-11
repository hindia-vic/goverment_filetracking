from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, date
from calendar import monthrange

from register.models import File, FileRequest, Department


@login_required
def file_queue_position(request, file_uuid):
    """Show user their queue position for a file request"""
    file = get_object_or_404(File, uuid=file_uuid)
    
    # Get pending requests for this file, ordered by creation date
    pending_requests = FileRequest.objects.filter(
        file=file,
        status__in=['pending', 'ready_for_pickup']
    ).order_by('created_at')
    
    # Find user's position
    user_position = None
    total_pending = pending_requests.count()
    
    for idx, req in enumerate(pending_requests, 1):
        if req.requesting_user == request.user:
            user_position = idx
            break
    
    # Get other users in queue
    queue = []
    for req in pending_requests[:5]:
        queue.append({
            'position': list(pending_requests).index(req) + 1,
            'username': req.requesting_user.username,
            'status': req.status,
            'is_current_user': req.requesting_user == request.user,
        })
    
    context = {
        'file': file,
        'user_position': user_position,
        'total_pending': total_pending,
        'queue': queue,
    }
    
    return render(request, 'register/user_experience/queue_position.html', context)


@login_required
def api_queue_position(request, file_uuid):
    """API endpoint for queue position"""
    file = get_object_or_404(File, uuid=file_uuid)
    
    pending_requests = FileRequest.objects.filter(
        file=file,
        status__in=['pending', 'ready_for_pickup']
    ).order_by('created_at')
    
    user_position = None
    total_pending = pending_requests.count()
    
    for idx, req in enumerate(pending_requests, 1):
        if req.requesting_user == request.user:
            user_position = idx
            break
    
    return JsonResponse({
        'file': file.reference,
        'user_position': user_position,
        'total_pending': total_pending,
    })


@login_required
def file_calendar_view(request):
    """Calendar view showing file availability"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get first and last day of month
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    # Get files with movements in this month
    from register.models import FileMovement
    movements = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file', 'from_user', 'to_user')
    
    # Group by date
    calendar_events = {}
    for movement in movements:
        day = movement.created_at.date().day
        if day not in calendar_events:
            calendar_events[day] = []
        calendar_events[day].append({
            'file': movement.file.reference,
            'action': movement.get_action_display(),
            'from_user': movement.from_user.username if movement.from_user else None,
            'to_user': movement.to_user.username if movement.to_user else None,
        })
    
    # Get overdue files for highlighting
    overdue_files = File.objects.filter(status='overdue')
    
    # Generate calendar days
    import calendar as cal
    month_days = cal.monthcalendar(year, month)
    
    context = {
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'calendar_days': month_days,
        'calendar_events': calendar_events,
        'overdue_files': overdue_files,
    }
    
    return render(request, 'register/user_experience/file_calendar.html', context)


@login_required
def api_file_calendar(request):
    """API endpoint for file calendar data"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    from register.models import FileMovement
    movements = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file')
    
    events = []
    for movement in movements:
        events.append({
            'date': movement.created_at.date().isoformat(),
            'file': movement.file.reference,
            'action': movement.action,
        })
    
    return JsonResponse({'events': events})


@login_required
def toggle_theme(request):
    """Toggle between light and dark mode"""
    if request.method == 'POST':
        theme = request.POST.get('theme', 'light')
        
        # Store in session
        request.session['theme'] = theme
        
        return JsonResponse({'theme': theme})
    
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def file_workflow_status(request, file_uuid):
    """Visual workflow status for a file"""
    file = get_object_or_404(File, uuid=file_uuid)
    
    # Get all requests for this file
    requests = FileRequest.objects.filter(
        file=file
    ).order_by('-created_at')[:10]
    
    # Get current movement history
    from register.models import FileMovement
    movements = FileMovement.objects.filter(
        file=file
    ).order_by('-created_at')[:10]
    
    context = {
        'file': file,
        'requests': requests,
        'movements': movements,
    }
    
    return render(request, 'register/user_experience/workflow_status.html', context)


@login_required
def dashboard_quick_actions(request):
    """Quick actions for dashboard"""
    from django.contrib.auth.models import User
    
    user = request.user
    
    # Get pending requests (where user is the requester)
    my_pending_requests = FileRequest.objects.filter(
        requesting_user=user,
        status__in=['pending', 'ready_for_pickup', 'handed_over']
    ).count()
    
    # Get my active files
    my_files = File.objects.filter(current_holder=user).count()
    
    # Get overdue files
    overdue = File.objects.filter(
        current_holder=user,
        status='overdue'
    ).count()
    
    # Get pending return confirmations
    pending_returns = FileRequest.objects.filter(
        requesting_user=user,
        status='pending_return'
    ).count()
    
    return JsonResponse({
        'my_pending_requests': my_pending_requests,
        'my_files': my_files,
        'overdue': overdue,
        'pending_returns': pending_returns,
    })