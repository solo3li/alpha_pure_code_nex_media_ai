from django.urls import path
from . import views

app_name = 'text_to_voice'

urlpatterns = [
    path('', views.home, name='home'),
    path('generate_audio/', views.generate_audio, name='generate_audio'),
    path('check_status/<uuid:processing_id>/', views.check_tts_status, name='check_tts_status'),
    path('download_audio/<str:filename>', views.download_audio, name='download_audio'),
    path('voice_demo/<int:voice_id>/', views.serve_voice_demo, name='serve_voice_demo'),
    path('get_trials_left/', views.get_trials_left_endpoint, name='get_trials_left'),
    path('history/', views.get_history, name='get_history'),
]