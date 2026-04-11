import calendar
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from calendar import monthcalendar, monthrange
from .models import FileMovement, File

@login_required
def file_calendar(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    # ✅ Correct calendar generation (Monday start)
    month_days = monthcalendar(year, month)

    # ✅ Correct date filtering
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    movements = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file', 'from_user', 'to_user')

    # ✅ Events preprocessing
    events_by_date = {}
    for movement in movements:
        date_key = movement.created_at.date().isoformat()
        events_by_date.setdefault(date_key, []).append({
            'title': movement.file.reference,
            'type': movement.action,
        })

    overdue_files = File.objects.filter(status='overdue')

    # ✅ Month name for UI
    month_name = calendar.month_name[month]

    context = {
        'month_days': month_days,
        'events_by_date': events_by_date,
        'year': year,
        'month': month,
        'month_name': month_name,
        'overdue_files': overdue_files,
    }

    return render(request, 'register/file_calendar.html', context)


@login_required
def api_file_calendar(request):
    """API for file calendar events"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    
    movements = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file')
    
    events = []
    for m in movements:
        events.append({
            'date': m.created_at.date().isoformat(),
            'file': m.file.reference,
            'action': m.action,
        })
    
    return JsonResponse({'events': events})


@login_required
def toggle_theme(request):
    """Toggle dark/light mode"""
    if request.method == 'POST':
        theme = request.POST.get('theme', 'light')
        request.session['theme'] = theme
        return JsonResponse({'theme': theme})
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def get_theme(request):
    """Get current theme"""
    theme = request.session.get('theme', 'light')
    return JsonResponse({'theme': theme})