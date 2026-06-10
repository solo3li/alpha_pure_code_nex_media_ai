 
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='ha'),
    path('upload/', views.upload_file, name='upload_file'),
    path('generate/', views.generate_caption, name='generate_caption'),
    path('get_trials_left/', views.get_trials_left_api, name='get_trials_left'),
]