from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from .models import SleepLog, Habit, HabitLog


def home(request):
    return render(request, 'home.html')

def sleep(request):
    sleep_records = SleepLog.objects.all()
    return render(request, 'sleep.html', {"sleep_records": sleep_records})

def habits(request):
    habit_list = Habit.objects.all()
    habit_records = HabitLog.objects.all()
    return render(request, 'habits.html', {"habit_records": habit_records, "habit_list": habit_list})

