# text_to_cartoon/urls.py
from django.urls import path
from . import views

app_name = 'text_to_cartoon'

urlpatterns = [
    # Main pages
    path('', views.home, name='cartoon_home'),
    
    # Processing endpoints
    path('upload/', views.upload_prompt, name='cartoon_upload'),
    path('generate/', views.generate_cartoon, name='cartoon_generate'),
    
    # Status and queue management
    path('status/<str:processing_id>/', views.processing_status, name='cartoon_status'),
    path('queue/', views.processing_queue, name='processing_queue'),
    path('retry/<str:processing_id>/', views.retry_processing, name='retry_processing'),
    
    # Results
    path('result/<int:image_data_id>/', views.get_image_result, name='cartoon_result'),
    
    # API endpoints
    path('api/trials-left/', views.get_trials_left_api, name='get_cartoon_trials'),
]