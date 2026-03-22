import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.urls import reverse


class User(AbstractUser):
    birthday = models.DateField(null=True, blank=True)
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("ON", "Other/Non-binary"),
        ("PN", "Prefer not to say")
    ]
    gender = models.CharField(max_length=2, choices=GENDER_CHOICES, default="PN")


class SleepLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sleep')
    date = models.DateField(default=timezone.now)
    bedtime = models.DateTimeField()
    waketime = models.DateTimeField()
    quality = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    comment = models.TextField(blank=True)

    # @property -> To make duration not a function but an attribute -> log.duration
    @property
    def duration(self):
        if self.waketime and self.bedtime:
            delta = self.waketime - self.bedtime
            total_seconds = delta.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        return "0h"

    def get_absolute_url(self):
        return reverse("sleep-detail", args=[str(self.id)])

class Habit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)

    def is_done_on(self, date):
        return self.logs.filter(date=date, if_done=True).exists()

    def get_absolute_url(self):
        return reverse("habit-detail", args=[str(self.id)])

class HabitLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='logs')
    date = models.DateField()
    if_done = models.BooleanField(default=False)
    def get_absolute_url(self):
        return reverse("habit-log-detail", args=[str(self.id)])
