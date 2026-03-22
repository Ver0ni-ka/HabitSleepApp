import datetime
from django.contrib import messages
from datetime import timedelta

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from .models import SleepLog, Habit, HabitLog, User
from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from .forms import MyUserCreationForm, LoginForm, ProfileEditForm
from django.http import JsonResponse
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
    return render(request, 'home.html')
@login_required
def sleep_view(request):
    date_today = timezone.now().date()
    sleep_log, created = SleepLog.objects.get_or_create(user=request.user, date=date_today, defaults={
            'bedtime': (timezone.now() - timedelta(days=1)).replace(hour=23, minute=0),
            'waketime': timezone.now().replace(hour=7, minute=0),
            'quality': 5})
    history = SleepLog.objects.filter(user=request.user).order_by('-date')[:7]

    if request.method == 'POST':
        bed_time_str = request.POST.get('bedtime')
        wake_time_str = request.POST.get('waketime')

        b_time = datetime.datetime.strptime(bed_time_str, '%H:%M').time()
        w_time = datetime.datetime.strptime(wake_time_str, '%H:%M').time()

        dt_bed = timezone.make_aware(datetime.datetime.combine(date_today, b_time))
        dt_wake = timezone.make_aware(datetime.datetime.combine(date_today, w_time))

        if dt_wake <= dt_bed:
            dt_bed -= datetime.timedelta(days=1)

        sleep_log.bedtime = dt_bed
        sleep_log.waketime = dt_wake
        sleep_log.quality = request.POST.get('quality', 5)
        comment = request.POST.get('comment', '')
        sleep_log.comment = comment
        sleep_log.save()

        return JsonResponse({'status': 'updated', 'duration': sleep_log.duration})

    return render(request, 'sleep.html', {'sleep_log': sleep_log, 'history': history})
def sleep_edit(request, pk):
    sleep_log = get_object_or_404(SleepLog, pk=pk, user=request.user)

    if request.method == "POST":
        bed_time_str = request.POST.get('bedtime')
        wake_time_str = request.POST.get('waketime')
        b_time = datetime.datetime.strptime(bed_time_str, '%H:%M').time()
        w_time = datetime.datetime.strptime(wake_time_str, '%H:%M').time()
        date = sleep_log.date
        dt_bed = timezone.make_aware(datetime.datetime.combine(date, b_time))
        dt_wake = timezone.make_aware(datetime.datetime.combine(date, w_time))
        if dt_wake <= dt_bed:
            dt_bed -= timedelta(days=1)
        sleep_log.bedtime = dt_bed
        sleep_log.waketime = dt_wake
        sleep_log.quality = request.POST.get('quality', 5)
        sleep_log.comment = request.POST.get('comment', '')
        sleep_log.save()

        return redirect('sleep-page')

    return render(request, 'sleep_form.html', {'object': sleep_log})


@login_required
def habit_tracker_view(request):
    today = datetime.date.today()
    date_list = [today - datetime.timedelta(days=x) for x in range(6, -1, -1)]
    habits = Habit.objects.filter(user=request.user, status=True)
    habit_count = Habit.objects.filter(user=request.user).count()
    logs = HabitLog.objects.filter(
        habit__in=habits,
        date__range=[date_list[0], date_list[-1]]
    ).values('habit_id', 'date', 'if_done')
    logs_dict = {(log['habit_id'], log['date']): log['if_done'] for log in logs}
    tracker_data = []
    for habit in habits:
        history = []
        for d in date_list:
            history.append({
                'date': d.strftime('%Y-%m-%d'),
                'is_done': logs_dict.get((habit.id, d), False)
            })
        tracker_data.append({'habit': habit, 'history': history})
    return render(request, 'habits.html', {'date_list': date_list, 'tracker_data': tracker_data, 'habit_count': habit_count})
class HabitCreateView(LoginRequiredMixin, CreateView):
    model = Habit
    fields = ['name', 'description', 'status']
    template_name = 'habit_form.html'
    success_url = reverse_lazy('habits-page')
    def form_valid(self, form):
        habit_count = Habit.objects.filter(user=self.request.user).count()
        if habit_count >= 12:
            messages.error(self.request, "You cannot add more than 12 habits.")
            return redirect('habits-page')
        form.instance.user = self.request.user
        return super().form_valid(form)

class HabitUpdateView(LoginRequiredMixin, UpdateView):
    model = Habit
    fields = ['name', 'description', 'status']
    template_name = 'habit_form.html'
    success_url = reverse_lazy('habits-page')
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)


@login_required
def delete_habit(request, habit_id):
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    if request.method == "POST":
        habit.delete()
    return redirect("habits-page")


@login_required
def all_habit_list_view(request):
    all_habits = Habit.objects.filter(user=request.user)
    return render(request, 'habits_all.html', {'habit_list': all_habits})

@login_required
def toggle_habit(request, habit_id, date):
    date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    log, created = HabitLog.objects.get_or_create(
        habit=habit,
        date=date_obj)
    log.if_done = not log.if_done
    log.save()
    return JsonResponse({'status': 'success', 'if_done': log.if_done})