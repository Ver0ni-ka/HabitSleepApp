from django.contrib import admin

from HabitsAndSleep.models import SleepLog, Habit, HabitLog


# Register your models here.
admin.site.register(SleepLog)
admin.site.register(Habit)
admin.site.register(HabitLog)