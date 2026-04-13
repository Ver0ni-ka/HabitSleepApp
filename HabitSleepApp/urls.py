"""
URL configuration for HabitSleepApp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from HabitsAndSleep import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile-edit/', views.edit_profile, name='edit-profile'),
    path('profile-edit/password', views.change_password, name='change-password'),
    path('accounts/', include('allauth.urls')),
    path('', views.home, name='home'),
    path('sleep/', views.sleep_view, name='sleep-page'),
    path('sleep/edit/<uuid:pk>/', views.sleep_edit, name='sleep-edit'),
    path('habits/', views.habit_tracker_view, name='habits-page'),
    path('habits/add/', views.HabitCreateView.as_view(), name='habit-add'),
    path('habits/toggle/<uuid:habit_id>/<str:date>/', views.toggle_habit, name='toggle-habit'),
    path("habits/<uuid:habit_id>/delete/", views.delete_habit, name="habit-delete"),
    path("habits/all", views.all_habit_list_view, name="habit-list"),
]
