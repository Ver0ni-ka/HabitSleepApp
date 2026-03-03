from django.shortcuts import render, redirect
from .models import SleepLog, Habit, HabitLog
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import MyUserCreationForm, LoginForm


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
        next_url = request.POST.get('next') or 'home'
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect(next_url)
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


def home(request):
    return render(request, 'home.html')

@login_required
def sleep(request):
    sleep_records = SleepLog.objects.filter(user=request.user)
    return render(request, 'sleep.html', {"sleep_records": sleep_records})

@login_required
def habits(request):
    habit_list = Habit.objects.filter(user=request.user)
    habit_records = HabitLog.objects.filter(habit__user=request.user)
    return render(request, 'habits.html', {"habit_records": habit_records, "habit_list": habit_list})