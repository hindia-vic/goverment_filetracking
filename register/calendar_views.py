import calendar
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import FileMovement, File

@login_required
def file_calendar(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))

    # ✅ Use Calendar with Monday start (firstweekday=0)
    cal = calendar.Calendar(firstweekday=0)
    # ✅ Produce list of weeks, each week is list of 7 integers (0 = empty day)
    month_days = cal.monthdayscalendar(year, month)

    # ✅ Correct date filtering
    first_day = date(year, month, 1)
    from calendar import monthrange
    last_day = date(year, month, monthrange(year, month)[1])

    # ✅ Events queryset filtered by month
    events = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file', 'from_user', 'to_user')

    # ✅ Month name for UI
    month_name = calendar.month_name[month]

    context = {
        'month_days': month_days,
        'events': events,
        'year': year,
        'month': month,
        'month_name': month_name,
    }

    return render(request, 'register/file_calendar.html', context)


@login_required
def api_file_calendar(request):
    """API for file calendar events"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    first_day = date(year, month, 1)
    from calendar import monthrange
    last_day = date(year, month, monthrange(year, month)[1])
    
    events = FileMovement.objects.filter(
        created_at__date__gte=first_day,
        created_at__date__lte=last_day
    ).select_related('file')
    
    events_list = []
    for m in events:
        events_list.append({
            'date': m.created_at.date().isoformat(),
            'file': m.file.reference,
            'action': m.action,
        })
    
    return JsonResponse({'events': events_list})


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