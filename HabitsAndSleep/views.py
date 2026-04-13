import calendar
import datetime
from django.contrib import messages
from datetime import timedelta

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from .models import SleepLog, Habit, HabitLog, User
from django.views.generic import CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .forms import MyUserCreationForm, LoginForm, ProfileEditForm
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

# Authentication
def register_view(request):
    if request.method == "POST":
        form = MyUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')
    else:
        form = MyUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    error_message = None
    next_url = request.GET.get('next', '')
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            password = form.cleaned_data.get("password")
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect(next_url or 'home')
            else:
                error_message = "Invalid credentials"
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form, 'error': error_message, 'next': next_url})

@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect('login')
    else:
        return redirect('home')

@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect('edit-profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})

def home(request):
    context = {}
    if request.user.is_authenticated:
        date_today = timezone.localdate()
        sleep_log, created = get_or_create_sleep_log(request.user, date_today)
        habits = Habit.objects.filter(user=request.user, status=True)
        logs = HabitLog.objects.filter(habit__in=habits, date=date_today).values('habit_id', 'if_done')
        logs_dict = {log['habit_id']: log['if_done'] for log in logs}
        habit_entries = [{'habit': habit, 'is_done': logs_dict.get(habit.id, False)} for habit in habits]
        context.update({
            'sleep_log': sleep_log,
            'active_habits': habit_entries,
            'today_str': date_today.strftime('%Y-%m-%d'),
            'today_display': date_today.strftime('%B %d, %Y'),
        })
    return render(request, 'home.html', context)


def build_default_sleep_values(log_date):
    bedtime = timezone.make_aware(
        datetime.datetime.combine(log_date - timedelta(days=1), datetime.time(23, 0))
    )
    waketime = timezone.make_aware(
        datetime.datetime.combine(log_date, datetime.time(7, 0))
    )
    return {
        'bedtime': bedtime,
        'waketime': waketime,
        'quality': 5,
    }


def get_or_create_sleep_log(user, log_date):
    return SleepLog.objects.get_or_create(
        user=user,
        date=log_date,
        defaults=build_default_sleep_values(log_date),
    )


def update_sleep_log_from_post(sleep_log, post_data):
    bed_time_str = post_data.get('bedtime')
    wake_time_str = post_data.get('waketime')
    b_time = datetime.datetime.strptime(bed_time_str, '%H:%M').time()
    w_time = datetime.datetime.strptime(wake_time_str, '%H:%M').time()
    log_date = sleep_log.date
    dt_bed = timezone.make_aware(datetime.datetime.combine(log_date, b_time))
    dt_wake = timezone.make_aware(datetime.datetime.combine(log_date, w_time))

    if dt_wake <= dt_bed:
        dt_bed -= timedelta(days=1)

    sleep_log.bedtime = dt_bed
    sleep_log.waketime = dt_wake
    sleep_log.quality = post_data.get('quality', 5)
    sleep_log.comment = post_data.get('comment', '')
    sleep_log.save()
    return sleep_log


def get_sleep_timeline_metrics(sleep_log):
    timeline_start = 21 * 60
    timeline_end = (24 * 60) + (13 * 60)
    total_minutes = timeline_end - timeline_start
    bedtime = timezone.localtime(sleep_log.bedtime)
    waketime = timezone.localtime(sleep_log.waketime)

    def adjust_minutes(dt):
        m = dt.hour * 60 + dt.minute
        return m + 1440 if m < timeline_start else m

    start_m = adjust_minutes(bedtime)
    end_m = adjust_minutes(waketime)

    clamped_start = max(timeline_start, min(start_m, timeline_end))
    clamped_end = max(clamped_start, min(end_m, timeline_end))

    left_pct = ((clamped_start - timeline_start) / total_minutes) * 100
    width_pct = max(((clamped_end - clamped_start) / total_minutes) * 100, 2)

    return {
        'left_pct': round(left_pct, 3),
        'width_pct': round(width_pct, 3),
        'bedtime_display': bedtime.strftime('%H:%M'),
        'waketime_display': waketime.strftime('%H:%M'),
    }


def parse_date_params(request):
    view = request.GET.get('view') or request.POST.get('view') or 'weekly'
    week_change = 0
    day_change = 0
    try:
        wc_val = request.GET.get('week_change') or request.POST.get('week_change')
        if wc_val:
            week_change = int(wc_val)
        dc_val = request.GET.get('day_change') or request.POST.get('day_change')
        if dc_val:
            day_change = int(dc_val)
    except (TypeError, ValueError):
        pass
    return view, week_change, day_change

def get_sleep_tracker_context(request, selected_log=None):
    today = timezone.localdate()
    view, week_change, day_change = parse_date_params(request)
    if view not in ['weekly', 'monthly', 'yearly']:
        view = 'weekly'

    start_date, end_date, date_list = get_date_range(view, today, week_change, day_change)
    today_log, _ = get_or_create_sleep_log(request.user, today)

    if view == 'yearly':
        logs = SleepLog.objects.filter(
            user=request.user,
            date__year=start_date.year
        ).order_by('date')
        
        monthly_data = {m: [] for m in range(1, 13)}
        for log in logs:
            monthly_data[log.date.month].append(log)
        
        logs_by_date = {}
    else:
        logs = SleepLog.objects.filter(
            user=request.user,
            date__range=[start_date, end_date]
        ).order_by('date')
        logs_by_date = {log.date: log for log in logs}

    logs_by_id = {str(log.id): log for log in logs}
    logs_by_id[str(today_log.id)] = today_log
    if not view == 'yearly':
        logs_by_date[today] = today_log

    selected_id = request.GET.get('selected') or request.POST.get('selected') or ''
    selected_date_raw = request.GET.get('selected_date') or request.POST.get('selected_date') or ''

    if selected_log is None and selected_id:
        selected_log = logs_by_id.get(selected_id)
        if selected_log is None:
            selected_log = SleepLog.objects.filter(user=request.user, pk=selected_id).first()

    if selected_log is None and selected_date_raw:
        try:
            selected_date = datetime.datetime.strptime(selected_date_raw, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
        selected_log, _ = get_or_create_sleep_log(request.user, selected_date)

    if selected_log is None:
        selected_log = today_log

    if not view == 'yearly' and selected_log.date not in logs_by_date:
        logs_by_date[selected_log.date] = selected_log

    tracker_rows = []
    for d in date_list:
        if view == 'yearly':
            is_future = (d.year, d.month) > (today.year, today.month)
            is_today = (d.year, d.month) == (today.year, today.month)
            month_logs = monthly_data.get(d.month, [])
            
            avg_duration_str = "—"
            avg_quality = "—"
            if month_logs:
                total_minutes = 0
                total_quality = 0
                for log in month_logs:
                    delta = log.waketime - log.bedtime
                    total_minutes += delta.total_seconds() / 60
                    total_quality += log.quality
                avg_min = total_minutes / len(month_logs)
                avg_duration_str = f"{int(avg_min // 60)}h {int(avg_min % 60)}m"
                avg_quality = round(total_quality / len(month_logs), 1)

            row = {
                'date': d,
                'date_iso': d.strftime('%Y-%m-%d'),
                'label': d.strftime('%b'),
                'is_today': is_today,
                'is_future': is_future,
                'is_selected': False,
                'has_log': len(month_logs) > 0,
                'avg_duration': avg_duration_str,
                'avg_quality': avg_quality,
                'is_yearly': True,
            }
        else:
            sleep_log = logs_by_date.get(d)
            if d == today:
                sleep_log = today_log
            
            is_future = d > today
            is_selected = not is_future and sleep_log is not None and sleep_log.id == selected_log.id
            
            if d == today:
                label = 'Today'
            elif d == today - timedelta(days=1):
                label = 'Yesterday'
            elif d == today + timedelta(days=1):
                label = 'Tomorrow'
            else:
                label = d.strftime('%d.%m')

            row = {
                'date': d,
                'date_iso': d.strftime('%Y-%m-%d'),
                'label': label,
                'sleep_log': sleep_log,
                'has_log': sleep_log is not None,
                'is_today': d == today,
                'is_future': is_future,
                'is_selected': is_selected,
                'edit_query': f"?view={view}&week_change={week_change}&day_change={day_change}&selected_date={d.strftime('%Y-%m-%d')}" if not is_future else None,
                'is_yearly': False,
            }

            if sleep_log is not None:
                row.update({
                    'duration': sleep_log.duration,
                    **get_sleep_timeline_metrics(sleep_log),
                })

        tracker_rows.append(row)

    return {
        'sleep_log': selected_log,
        'today_sleep_log': today_log,
        'tracker_rows': tracker_rows,
        'start_date': start_date,
        'end_date': end_date,
        'week_change': week_change,
        'day_change': day_change,
        'view': view,
        'is_future_period': end_date > today,
        'today': today,
        'selected_is_today': selected_log.date == today,
        'selected_label': 'Today' if selected_log.date == today else selected_log.date.strftime('%d.%m.%Y'),
        'selected_date_iso': selected_log.date.strftime('%Y-%m-%d'),
        'hour_labels': [
            '21', '22', '23',
            '00', '01', '02', '03', '04', '05',
            '06', '07', '08', '09', '10', '11',
            '12', '13',
        ],
    }


@login_required
def sleep_view(request):
    context = get_sleep_tracker_context(request)
    
    # Server-side check to prevent adding sleep for future dates
    if request.method == 'POST':
        if context['view'] == 'yearly':
            return JsonResponse({'status': 'error', 'message': 'Yearly view cannot be saved'}, status=400)
        target_log = context['sleep_log']
        if target_log.date > timezone.localdate():
            return JsonResponse({'status': 'error', 'message': 'Future dates not allowed'}, status=400)
            
        update_sleep_log_from_post(target_log, request.POST)
        return JsonResponse({
            'status': 'updated',
            'duration': target_log.duration,
            'redirect_url': f"{reverse_lazy('sleep-page')}?view={context['view']}&week_change={context['week_change']}"
        })

    return render(request, 'sleep.html', context)

@login_required
def is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


def get_date_range(view, today, week_change, day_change):
    if view == 'monthly':
        month_offset = (today.month - 1) + week_change
        year = today.year + (month_offset // 12)
        month = (month_offset % 12) + 1
        start = datetime.date(year, month, 1)
        days_in_month = calendar.monthrange(year, month)[1]
        end = datetime.date(year, month, days_in_month)
        date_list = [start + timedelta(days=x) for x in range(days_in_month)]
        return start, end, date_list
    elif view == 'yearly':
        year = today.year + week_change
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        date_list = [datetime.date(year, month, 1) for month in range(1, 13)]
        return start, end, date_list
    elif view == 'daily':
        target_day = today + timedelta(days=day_change)
        return target_day, target_day, [target_day]
    else: # weekly
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_change)
        end = start + timedelta(days=6)
        date_list = [start + timedelta(days=x) for x in range(7)]
        return start, end, date_list

def get_habit_tracker_context(request):
    today = timezone.localdate()
    view, week_change, day_change = parse_date_params(request)
    if view not in ['daily', 'weekly', 'monthly', 'yearly']:
        view = 'weekly'

    start_of_week, end_of_week, date_list = get_date_range(view, today, week_change, day_change)

    habits = Habit.objects.filter(user=request.user, status=True)
    habit_count = Habit.objects.filter(user=request.user).count()
    
    if view == 'yearly':
        logs = HabitLog.objects.filter(
            habit__in=habits,
            date__range=[start_of_week, end_of_week],
            if_done=True
        ).values('habit_id', 'date')
        logs_dict = {}
        for log in logs:
            key = (log['habit_id'], log['date'].month)
            logs_dict[key] = logs_dict.get(key, 0) + 1
    else:
        logs = HabitLog.objects.filter(
            habit__in=habits,
            date__range=[start_of_week, end_of_week]
        ).values('habit_id', 'date', 'if_done')
        logs_dict = {(log['habit_id'], log['date']): log['if_done'] for log in logs}

    tracker_data = []
    for habit in habits:
        history = []
        for d in date_list:
            if view == 'yearly':
                is_future = (d.year, d.month) > (today.year, today.month)
                is_today = (d.year, d.month) == (today.year, today.month)
                if is_future:
                    display = '—'
                else:
                    total_days = today.day if is_today else calendar.monthrange(d.year, d.month)[1]
                    done_days = logs_dict.get((habit.id, d.month), 0)
                    display = f"{done_days}/{total_days}"
                history.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'is_done': False,
                    'display': display,
                    'is_future': is_future,
                    'is_today': is_today,
                    'is_yearly': True,
                })
            else:
                history.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'is_done': logs_dict.get((habit.id, d), False),
                    'display': None,
                    'is_future': d > today,
                    'is_today': d == today,
                    'is_yearly': False,
                })
        tracker_data.append({'habit': habit, 'history': history})

    return {
        'date_list': date_list,
        'tracker_data': tracker_data,
        'habit_count': habit_count,
        'week_change': week_change,
        'day_change': day_change,
        'start_date': start_of_week,
        'end_date': end_of_week,
        'view': view,
        'today': today,
        'today_month': today.month,
        'today_year': today.year,
    }


def habit_tracker_view(request):
    context = get_habit_tracker_context(request)
    return render(request, 'habits.html', context)
class HabitCreateView(LoginRequiredMixin, CreateView):
    model = Habit
    fields = ['name', 'description', 'status']
    template_name = 'habit_form.html'
    success_url = reverse_lazy('habits-page')
    def get(self, request, *args, **kwargs):
        if not is_htmx(request):
            return redirect('habits-page')
        return super().get(request, *args, **kwargs)
    def form_valid(self, form):
        habit_count = Habit.objects.filter(user=self.request.user).count()
        if habit_count >= 12:
            messages.error(self.request, "You cannot add more than 12 habits.")
            return redirect('habits-page')
        form.instance.user = self.request.user
        response = super().form_valid(form)
        if is_htmx(self.request):
            hx_response = HttpResponse('<div id="habitModalContent" hx-swap-oob="innerHTML"></div>')
            hx_response['HX-Trigger'] = 'refresh-habits'
            return hx_response
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = self.request.GET.get('view') or 'weekly'
        context['week_change'] = self.request.GET.get('week_change') or 0
        context['day_change'] = self.request.GET.get('day_change') or 0
        context['is_htmx'] = is_htmx(self.request)
        return context


class HabitUpdateView(LoginRequiredMixin, UpdateView):
    model = Habit
    fields = ['name', 'description', 'status']
    template_name = 'habit_form.html'
    success_url = reverse_lazy('habits-page')
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)
    def get(self, request, *args, **kwargs):
        if not is_htmx(request):
            return redirect('habits-page')
        return super().get(request, *args, **kwargs)
    def form_valid(self, form):
        response = super().form_valid(form)
        if is_htmx(self.request):
            hx_response = HttpResponse('<div id="habitModalContent" hx-swap-oob="innerHTML"></div>')
            hx_response['HX-Trigger'] = 'refresh-habits'
            return hx_response
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = self.request.GET.get('view') or 'weekly'
        context['week_change'] = self.request.GET.get('week_change') or 0
        context['day_change'] = self.request.GET.get('day_change') or 0
        context['is_htmx'] = is_htmx(self.request)
        return context



@login_required
def delete_habit(request, habit_id):
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    if request.method == "POST":
        habit.delete()
        if is_htmx(request):
            hx_response = HttpResponse('<div id="habitModalContent" hx-swap-oob="innerHTML"></div>')
            hx_response['HX-Trigger'] = 'refresh-habits'
            return hx_response
    return redirect("habits-page")


@login_required
def all_habit_list_view(request):
    if not is_htmx(request):
        return redirect('habits-page')
    all_habits = Habit.objects.filter(user=request.user)
    context = {
        'habit_list': all_habits,
        'view': request.GET.get('view') or request.POST.get('view') or 'weekly',
        'week_change': request.GET.get('week_change') or request.POST.get('week_change') or 0,
        'day_change': request.GET.get('day_change') or request.POST.get('day_change') or 0,
        'is_htmx': True,
    }
    return render(request, 'habits_all.html', context)

@login_required
def toggle_habit(request, habit_id, date):
    date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    if date_obj > timezone.now().date():
        return JsonResponse({'status': 'error', 'message': 'Future dates are not allowed.'}, status=400)
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    log, created = HabitLog.objects.get_or_create(
        habit=habit,
        date=date_obj)
    log.if_done = not log.if_done
    log.save()
    return JsonResponse({'status': 'success', 'if_done': log.if_done})