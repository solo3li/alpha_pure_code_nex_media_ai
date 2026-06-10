# voice_to_text/urls.py
from django.urls import path
from . import views

app_name = 'voice_to_text'

urlpatterns = [
    # Main pages
    path('', views.home, name='audio_to_text_home'),
    
    # Processing endpoints


    path('process/', views.process_audio, name='process_audio'),
    # Results
    path('result/<int:text_data_id>/', views.get_text_result, name='voice_to_text_result'),
    
    # API endpoints
    path('api/trials-left/', views.get_trials_left_api, name='get_audio_trials'),
]