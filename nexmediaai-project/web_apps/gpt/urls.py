
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.home, name='home'),
    path('chat/', views.chat, name='chat'),
    path('get_trials_left/', views.get_trials_left_endpoint, name='get_trials_left'),
]