"""
Calendar view for file tracking - shows due dates and events
"""
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta, datetime
from calendar import monthrange, HTMLCalendar
from register.models import File, FileRequest


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
        
        # Get calendar events
        events = self.get_events(year, month)
        
        # Generate calendar
        cal = EventCalendar(events).formatmonth(year, month)
        
        # Get stats
        now = timezone.now()
        overdue_files = File.objects.filter(
            status__in=['checked_out', 'overdue'],
            due_date__lt=now
        ).count()
        
        upcoming_due = File.objects.filter(
            status='checked_out',
            due_date__gte=now,
            due_date__lte=now + timedelta(days=7)
        ).count()
        
        pending_returns = FileRequest.objects.filter(
            status='pending_return'
        ).count()
        
        return render(request, self.template_name, {
            'calendar': cal,
            'month': month,
            'year': year,
            'month_name': datetime(year, month, 1).strftime('%B'),
            'events': events,
            'overdue_files': overdue_files,
            'upcoming_due': upcoming_due,
            'pending_returns': pending_returns,
            'prev_month': self.get_prev_month(month, year),
            'next_month': self.get_next_month(month, year),
        })
    
    def get_events(self, year, month):
        """Get all events for the given month"""
        events = []
        
        # First day of month
        first_day = datetime(year, month, 1)
        # Last day of month
        last_day = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
        
        # Files with due dates in this month
        files = File.objects.filter(
            due_date__gte=first_day,
            due_date__lte=last_day
        ).select_related('current_holder', 'department')
        
        for f in files:
            events.append({
                'date': f.due_date.date(),
                'type': 'file_due',
                'title': f'File Due: {f.reference}',
                'description': f.title,
                'status': f.status,
                'holder': f.current_holder.get_full_name() if f.current_holder else 'N/A',
                'url': f'/register/files/{f.uuid}/',
            })
        
        # File requests with pickup dates
        requests = FileRequest.objects.filter(
            pickup_date__gte=first_day,
            pickup_date__lte=last_day,
            status__in=['ready_for_pickup', 'handed_over']
        ).select_related('file', 'requesting_user')
        
        for r in requests:
            events.append({
                'date': r.pickup_date.date(),
                'type': 'pickup',
                'title': f'Pickup: {r.file.reference}',
                'description': r.file.title,
                'user': r.requesting_user.get_full_name(),
                'url': f'/register/requests/{r.pk}/',
            })
        
        # Pending return confirmations
        return_reqs = FileRequest.objects.filter(
            status='pending_return'
        ).select_related('file', 'requesting_user')
        
        for r in return_reqs:
            # Add to first day of month as placeholder
            events.append({
                'date': first_day.date(),
                'type': 'return_pending',
                'title': f'Return Pending: {r.file.reference}',
                'description': r.file.title,
                'user': r.requesting_user.get_full_name(),
                'url': f'/register/requests/{r.pk}/verify-return/',
            })
        
        return events
    
    def get_prev_month(self, month, year):
        if month == 1:
            return {'month': 12, 'year': year - 1}
        return {'month': month - 1, 'year': year}
    
    def get_next_month(self, month, year):
        if month == 12:
            return {'month': 1, 'year': year + 1}
        return {'month': month + 1, 'year': year}


class EventCalendar(HTMLCalendar):
    """Custom calendar that displays events"""
    
    def __init__(self, events):
        super().__init__()
        self.events = events
    
    def formatday(self, day, weekday):
        """Format a day cell"""
        if day == 0:
            return '<td class="py-3"></td>'
        
        date = datetime(self.year, self.month, day).date()
        day_events = [e for e in self.events if e['date'] == date]
        
        html = f'<td class="py-3" style="vertical-align: top;">'
        html += f'<div class="date-number">{day}</div>'
        
        for event in day_events[:3]:  # Show max 3 events per day
            color = self.get_event_color(event['type'])
            html += f'''
            <a href="{event['url']}" class="event-badge" style="background:{color};font-size:10px;padding:2px 4px;border-radius:3px;display:block;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                {event['title'][:20]}...
            </a>
            '''
        
        if len(day_events) > 3:
            html += f'<small class="text-muted">+{len(day_events) - 3} more</small>'
        
        html += '</td>'
        return html
    
    def formatmonth(self, year, month):
        self.year, self.month = year, month
        return super().formatmonth(year, month)
    
    def get_event_color(self, event_type):
        colors = {
            'file_due': '#dc3545',      # Red for due
            'pickup': '#0dcaf0',         # Cyan for pickup
            'return_pending': '#ffc107', # Yellow for pending
        }
        return colors.get(event_type, '#6c757d')