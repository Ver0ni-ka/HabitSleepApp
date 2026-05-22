import calendar
import datetime
from datetime import timedelta
from allauth.socialaccount.models import SocialAccount
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, UpdateView
from .forms import DeleteAccountForm, LoginForm, MyUserCreationForm, ProfileEditForm, StyledPasswordChangeForm
from .models import Habit, HabitLog, SleepLog, User
from django.db.models import Min

MAX_HABITS = 12

def user_can_change_password(user):
    has_google_account = SocialAccount.objects.filter(user=user, provider='google').exists()
    return user.has_usable_password() and not has_google_account

def is_htmx(request):
    return request.headers.get('HX-Request') == 'true'

def close_modal(target_id, trigger=None, redirect_url=None):
    response = HttpResponse(f'<div id="{target_id}" hx-swap-oob="innerHTML"></div>')
    if trigger:
        response['HX-Trigger'] = trigger
    if redirect_url:
        response['HX-Redirect'] = redirect_url
    return response

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
    return render(request, 'accounts/register.html', {
        'form': form,
        'register_url': reverse('register'),
        'login_url': reverse('login'),
    })

def login_view(request):
    next_url = request.GET.get('next', '')
    if request.method != "POST":
        return render(request, 'accounts/login.html', {
            'form': LoginForm(),
            'error': None,
            'next': next_url,
            'login_url': reverse('login'),
            'register_url': reverse('register'),
            'hidden_fields': [{'name': 'next', 'value': next_url}],
        })

    form = LoginForm(request.POST)
    if not form.is_valid():
        return render(request, 'accounts/login.html', {
            'form': form,
            'error': None,
            'next': next_url,
            'login_url': reverse('login'),
            'register_url': reverse('register'),
            'hidden_fields': [{'name': 'next', 'value': next_url}],
        })

    email = form.cleaned_data.get("email")
    password = form.cleaned_data.get("password")
    user_obj = User.objects.filter(email=email).first()
    user = authenticate(request, username=user_obj.username, password=password) if user_obj else None

    if user is None:
        return render(request, 'accounts/login.html', {
            'form': form,
            'error': "Invalid credentials",
            'next': next_url,
            'login_url': reverse('login'),
            'register_url': reverse('register'),
            'hidden_fields': [{'name': 'next', 'value': next_url}],
        })

    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    if not form.cleaned_data.get('remember_me'):
        request.session.set_expiry(0)

    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect('home')

@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect('login')
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
    return render(request, 'accounts/edit_profile.html', {
        'form': form,
        'change_password_url': reverse('change-password-modal'),
        'delete_account_url': reverse('delete-account'),
        'can_change_password': user_can_change_password(request.user),
        'profile_email': request.user.email,
    })

@login_required
def change_password(request):
    if not is_htmx(request):
        return redirect('edit-profile')

    if not user_can_change_password(request.user):
        return render(request, 'accounts/change_password.html', {
            'form': None,
            'password_change_blocked': True,
        })

    if request.method == 'POST':
        form = StyledPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return HttpResponse('', headers={'HX-Trigger': 'password-changed'})
    else:
        form = StyledPasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {
        'form': form,
        'password_change_blocked': False,
    })


@login_required
def delete_account(request):
    if not request.user.has_usable_password():
        if is_htmx(request):
            return render(request, 'accounts/delete_account_form.html', {
                'form': None,
                'delete_account_blocked': True,
            })
        return redirect('edit-profile')
    if request.method == 'POST':
        form = DeleteAccountForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            if is_htmx(request):
                return close_modal('accountModalContent', redirect_url=reverse('login'))
            return redirect('home')
    else:
        form = DeleteAccountForm(request.user)

    if is_htmx(request):
        return render(request, 'accounts/delete_account_form.html', {'form': form,})

    return redirect('edit-profile')

def home(request):
    context = {}
    if request.user.is_authenticated:
        date_today = timezone.localdate()
        sleep_log, _ = get_or_create_sleep_log(request.user, date_today)
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


def default_sleep_data(log_date):
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
        defaults=default_sleep_data(log_date),
    )


def update_sleep_log(sleep_log, post_data):
    bed_time_str = post_data.get('bedtime')
    wake_time_str = post_data.get('waketime')
    b_time = datetime.datetime.strptime(bed_time_str, '%H:%M').time()
    w_time = datetime.datetime.strptime(wake_time_str, '%H:%M').time()
    log_date = sleep_log.date
    dt_bed = timezone.make_aware(datetime.datetime.combine(log_date, b_time))
    dt_wake = timezone.make_aware(datetime.datetime.combine(log_date, w_time))
    # Bedtime belongs to the previous day
    if dt_wake <= dt_bed:
        dt_bed -= timedelta(days=1)

    sleep_log.bedtime = dt_bed
    sleep_log.waketime = dt_wake
    sleep_log.quality = post_data.get('quality', 5)
    sleep_log.comment = post_data.get('comment', '')
    sleep_log.save()
    return sleep_log

# Values for sleep timeline
def sleep_timeline(sleep_log):
    timeline_start = datetime.time(21, 0)
    timeline_end = datetime.time(13, 0)
    bedtime = timezone.localtime(sleep_log.bedtime)
    waketime = timezone.localtime(sleep_log.waketime)
    current_timezone = timezone.get_current_timezone()
    window_start = timezone.make_aware(
        datetime.datetime.combine(sleep_log.date - timedelta(days=1), timeline_start),
        current_timezone,
    )
    window_end = timezone.make_aware(
        datetime.datetime.combine(sleep_log.date, timeline_end),
        current_timezone,
    )
    total_minutes = (window_end - window_start).total_seconds() / 60

    start_m = (bedtime - window_start).total_seconds() / 60
    end_m = (waketime - window_start).total_seconds() / 60
    clamped_start = max(0, min(start_m, total_minutes))
    clamped_end = max(clamped_start, min(end_m, total_minutes))
    left_pct = (clamped_start / total_minutes) * 100
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
    try:
        wc_val = request.GET.get('week_change') or request.POST.get('week_change')
        if wc_val:
            week_change = int(wc_val)
    except (TypeError, ValueError):
        pass
    return view, week_change

def get_selected_log(request, today):
    raw_date = request.GET.get('selected_date') or request.POST.get('selected_date')
    try:
        selected_date = datetime.datetime.strptime(raw_date, '%Y-%m-%d').date() if raw_date else today
    except ValueError:
        selected_date = today

    if selected_date > today:
        return get_or_create_sleep_log(request.user, today)[0]
    return get_or_create_sleep_log(request.user, selected_date)[0]


def sleep_context(request):
    today = timezone.localdate()
    view, week_change = parse_date_params(request)
    if view not in ('weekly', 'monthly', 'yearly'):
        view = 'weekly'
    start_date, end_date, date_list = tracker_date_range(view, today, week_change)
    today_log, _ = get_or_create_sleep_log(request.user, today)
    selected_log = get_selected_log(request, today)
    logs = SleepLog.objects.select_related('user').filter(user=request.user)
    if view == 'yearly':
        logs = logs.filter(date__year=start_date.year).order_by('date')
        monthly_data = {m: [l for l in logs if l.date.month == m] for m in range(1, 13)}
    else:
        logs_by_date = {log.date: log for log in logs.filter(date__range=[start_date, end_date])}
        logs_by_date[today] = today_log
        logs_by_date[selected_log.date] = selected_log

    tracker_rows = []
    for d in date_list:
        if view == 'yearly':
            month_logs = monthly_data.get(d.month, [])
            avg_duration = "-"
            avg_quality = "-"
            if month_logs:
                total_minutes = sum((log.waketime - log.bedtime).total_seconds() / 60 for log in month_logs)
                avg_minutes = total_minutes / len(month_logs)
                avg_duration = f"{int(avg_minutes // 60)}h {int(avg_minutes % 60)}m"
                avg_quality = round(sum(log.quality for log in month_logs) / len(month_logs), 1)

            tracker_rows.append({
                'date': d,
                'label': d.strftime('%b'),
                'is_yearly': True,
                'is_today': (d.year, d.month) == (today.year, today.month),
                'is_future': (d.year, d.month) > (today.year, today.month),
                'has_log': bool(month_logs),
                'avg_duration': avg_duration,
                'avg_quality': avg_quality,
            })
        else:
            sleep_log = logs_by_date.get(d)
            is_future = d > today
            labels = {
                today: 'Today',
                today - timedelta(days=1): 'Yesterday',
                today + timedelta(days=1): 'Tomorrow',
            }
            row = {
                'date': d,
                'label': labels.get(d, d.strftime('%d.%m')),
                'sleep_log': sleep_log,
                'is_today': d == today,
                'is_future': is_future,
                'is_yearly': False,
                'has_log': bool(sleep_log),
                'is_selected': not is_future and sleep_log and sleep_log.date == selected_log.date,
                'edit_query': f"?view={view}&week_change={week_change}&selected_date={d.strftime('%Y-%m-%d')}" if not is_future else None,
            }
            if sleep_log:
                row.update({'duration': sleep_log.duration, **sleep_timeline(sleep_log)})
            tracker_rows.append(row)

    return {
        'sleep_log': selected_log,
        'today_sleep_log': today_log,
        'tracker_rows': tracker_rows,
        'start_date': start_date,
        'end_date': end_date,
        'week_change': week_change,
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
    context = sleep_context(request)
    if request.method == 'POST':
        if context['view'] == 'yearly':
            return JsonResponse({'status': 'error', 'message': 'Yearly view cannot be saved'}, status=400)
        target_log = context['sleep_log']
        if target_log.date > timezone.localdate():
            return JsonResponse({'status': 'error', 'message': 'Future dates not allowed'}, status=400)

        update_sleep_log(target_log, request.POST)
        is_quick = request.POST.get('is_quick') == 'true'
        response_data = {
            'status': 'updated',
            'duration': target_log.duration,
        }
        if not is_quick:
            response_data['redirect_url'] = f"{reverse_lazy('sleep-page')}?view={context['view']}&week_change={context['week_change']}"
        return JsonResponse(response_data)

    return render(request, 'sleep.html', context)

def tracker_date_range(view, today, week_change):
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
    else:
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_change)
        end = start + timedelta(days=6)
        date_list = [start + timedelta(days=x) for x in range(7)]
        return start, end, date_list


def habit_history(habit, date_list, today, view, logs_dict):
    history = []
    for d in date_list:
        if view == 'yearly':
            is_future = (d.year, d.month) > (today.year, today.month)
            is_today = (d.year, d.month) == (today.year, today.month)
            if is_future:
                display = '-'
            else:
                total_days = today.day if is_today else calendar.monthrange(d.year, d.month)[1]
                done_days = logs_dict.get((habit.id, d.month), 0)
                display = f"{done_days}/{total_days}"
            history.append({
                'date': d.strftime('%Y-%m-%d'),
                'is_done': False,
                'display': display,
                'day_label': d.strftime('%b'),
                'is_future': is_future,
                'is_today': is_today,
                'is_yearly': True,
            })
        else:
            history.append({
                'date': d.strftime('%Y-%m-%d'),
                'is_done': logs_dict.get((habit.id, d), False),
                'display': None,
                'day_label': d.strftime('%d.%m %a'),
                'is_future': d > today,
                'is_today': d == today,
                'is_yearly': False,
            })
    return history

def habit_context(request):
    today = timezone.localdate()
    view, week_change = parse_date_params(request)
    if view not in ('weekly', 'monthly', 'yearly'):
        view = 'weekly'
    start_of_week, end_of_week, date_list = tracker_date_range(view, today, week_change)
    habits = Habit.objects.filter(user=request.user, status=True)
    habit_count = Habit.objects.filter(user=request.user).count()
    logs_qs = HabitLog.objects.filter(habit__in=habits, date__range=[start_of_week, end_of_week])
    if view == 'yearly':
        logs = logs_qs.filter(if_done=True).values('habit_id', 'date')
        logs_dict = {}
        for log in logs:
            key = (log['habit_id'], log['date'].month)
            logs_dict[key] = logs_dict.get(key, 0) + 1
    else:
        logs = logs_qs.values('habit_id', 'date', 'if_done')
        logs_dict = {(log['habit_id'], log['date']): log['if_done'] for log in logs}

    tracker_data = [
        {
            'habit': habit,
            'history': habit_history(habit, date_list, today, view, logs_dict)
        }
        for habit in habits
    ]

    return {
        'date_list': date_list,
        'tracker_data': tracker_data,
        'week_change': week_change,
        'start_date': start_of_week,
        'end_date': end_of_week,
        'view': view,
        'today': today,
        'today_month': today.month,
        'today_year': today.year,
        'can_add_habit': habit_count < MAX_HABITS,
    }


@login_required
def habit_tracker_view(request):
    context = habit_context(request)
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
        if Habit.objects.filter(user=self.request.user).count() >= MAX_HABITS:
            form.add_error(None, f"You cannot add more than {MAX_HABITS} habits.")
            return self.form_invalid(form)
        form.instance.user = self.request.user
        response = super().form_valid(form)
        if is_htmx(self.request):
            return close_modal('habitModalContent', trigger='refresh-habits')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = self.request.GET.get('view') or 'weekly'
        context['week_change'] = self.request.GET.get('week_change') or 0
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
            return close_modal('habitModalContent', trigger='refresh-habits')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['view'] = self.request.GET.get('view') or 'weekly'
        context['week_change'] = self.request.GET.get('week_change') or 0
        context['is_htmx'] = is_htmx(self.request)
        return context

@login_required
def delete_habit(request, habit_id):
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    if request.method == "POST":
        habit.delete()
        if is_htmx(request):
            return close_modal('habitModalContent', trigger='refresh-habits')
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
        'is_htmx': True,
    }
    return render(request, 'habits_all.html', context)

@login_required
def toggle_habit(request, habit_id, date):
    date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    if date_obj > timezone.localdate():
        return JsonResponse({'status': 'error', 'message': 'Future dates are not allowed.'}, status=400)
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    log, _ = HabitLog.objects.get_or_create(habit=habit, date=date_obj)
    log.if_done = not log.if_done
    log.save()
    return JsonResponse({'status': 'success', 'if_done': log.if_done})

@login_required
def report_page(request):
    chart_type = request.GET.get('chart', 'habits')
    if chart_type not in ('habits', 'sleep-profile', 'sleep-impact'):
        chart_type = 'habits'
    return render(request, 'reports.html', {'active_chart': chart_type})

@login_required
def report_data(request):
    today = timezone.localdate()

    habit_labels, habit_values = [], []
    habits = Habit.objects.filter(user=request.user, status=True)
    for habit in habits:
        first_date = HabitLog.objects.filter(habit=habit, if_done=True).aggregate(first=Min("date"))["first"]
        if not first_date:
            continue

        logs = HabitLog.objects.filter(habit=habit, date__range=[first_date, today])
        log_map = {log.date: log.if_done for log in logs}
        total = 0
        done = 0
        d = first_date
        while d <= today:
            total += 1
            if log_map.get(d) is True:
                done += 1
            d += timedelta(days=1)

        habit_labels.append(habit.name)
        habit_values.append(round(done / total, 2) if total else 0)

    sleep_dict = {}
    sleep_profile_map = {}
    sleep_logs = SleepLog.objects.filter(user=request.user).exclude(bedtime__isnull=True).exclude(waketime__isnull=True)
    for log in sleep_logs:
        duration = (log.waketime - log.bedtime).total_seconds() / 3600
        sleep_dict[log.date] = duration

        dt = timezone.localtime(log.bedtime)
        hour = dt.hour
        minute = dt.minute
        if minute < 15:
            rounded_hour, rounded_minute = hour, 0
        elif minute < 45:
            rounded_hour, rounded_minute = hour, 30
        else:
            rounded_hour, rounded_minute = (hour + 1) % 24, 0

        label = f"{rounded_hour:02d}:{rounded_minute:02d}"
        sleep_profile_map.setdefault(label, {"sum": 0, "count": 0})
        sleep_profile_map[label]["sum"] += duration
        sleep_profile_map[label]["count"] += 1

    def bedtime_sort(label):
        h, m = map(int, label.split(":"))
        return ((h - 18) % 24) * 60 + m

    sleep_profile_labels = sorted(sleep_profile_map.keys(), key=bedtime_sort)
    sleep_profile_values = [
        round(sleep_profile_map[label]["sum"] / sleep_profile_map[label]["count"], 2)
        for label in sleep_profile_labels
    ]
    sleep_profile_counts = [sleep_profile_map[label]["count"] for label in sleep_profile_labels]

    sleep_intervals = {
        "<4": [],
        "4-5.9": [],
        "6-6.9": [],
        "7-7.9": [],
        "8-8.9": [],
        "9-9.9": [],
        "10-11.9": [],
        "12+": [],
    }
    for log in HabitLog.objects.filter(habit__user=request.user, habit__status=True):
        sleep = sleep_dict.get(log.date)
        if sleep is None:
            continue
        if sleep < 4:
            sleep_intervals["<4"].append(1 if log.if_done else 0)
        elif sleep < 6:
            sleep_intervals["4-5.9"].append(1 if log.if_done else 0)
        elif sleep < 7:
            sleep_intervals["6-6.9"].append(1 if log.if_done else 0)
        elif sleep < 8:
            sleep_intervals["7-7.9"].append(1 if log.if_done else 0)
        elif sleep < 9:
            sleep_intervals["8-8.9"].append(1 if log.if_done else 0)
        elif sleep < 10:
            sleep_intervals["9-9.9"].append(1 if log.if_done else 0)
        elif sleep < 12:
            sleep_intervals["10-11.9"].append(1 if log.if_done else 0)
        else:
            sleep_intervals["12+"].append(1 if log.if_done else 0)

    return JsonResponse({
        "habits_chart": {
            "labels": habit_labels,
            "values": habit_values,
        },
        "sleep_profile": {
            "labels": sleep_profile_labels,
            "values": sleep_profile_values,
            "counts": sleep_profile_counts,
        },
        "sleep_impact": {
            "labels": list(sleep_intervals.keys()),
            "values": [round(sum(v) / len(v), 2) if v else 0 for v in sleep_intervals.values()],
            "counts": [len(v) for v in sleep_intervals.values()],
        },
    })
