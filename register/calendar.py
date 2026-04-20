"""
Calendar view for file tracking - shows due dates and events
Uses Python's calendar module with Monday start
"""
import calendar
from datetime import date, datetime
from django.db.models import Q
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from register.models import File, FileRequest, FileMovement


class FileCalendarView(LoginRequiredMixin, View):
    """Calendar view showing file due dates and events"""
    template_name = 'register/calendar.html'
    
    def get(self, request):
        # Get month/year from query params or use current
        try:
            month = int(request.GET.get('month', timezone.now().month))
            year = int(request.GET.get('year', timezone.now().year))
        except ValueError:
            month = timezone.now().month
            year = timezone.now().year
        
        # ✅ Calendar with Monday start (firstweekday=0)
        cal = calendar.Calendar(firstweekday=0)
        # ✅ Produce list of weeks, each week is list of 7 integers (0 = empty day)
        month_days = cal.monthdayscalendar(year, month)
        
        # ✅ Get first and last day of month
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        
        # ✅ Events queryset filtered by the given month
        movements = FileMovement.objects.filter(
            created_at__date__gte=first_day,
            created_at__date__lte=last_day
        ).select_related('file', 'to_user')
        
        # ✅ Files with due dates in this month
        due_files = File.objects.filter(
            due_date__gte=first_day,
            due_date__lte=last_day,
            status__in=['checked_out', 'overdue']
        ).select_related('current_holder')
        
        # ✅ All pending return requests (show all with pending status)
        return_pending_requests = FileRequest.objects.filter(
            Q(status='pending_return') | Q(status='handed_over')
        ).select_related('file', 'requesting_user')
        
        # ✅ Month name
        month_name = calendar.month_name[month]
        
        return render(request, self.template_name, {
            'month_days': month_days,
            'events': movements,
            'due_files': due_files,
            'return_pending_requests': return_pending_requests,
            'year': year,
            'month': month,
            'month_name': month_name,
        })