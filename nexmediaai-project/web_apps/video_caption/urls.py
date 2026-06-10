# video_caption/urls.py
from django.urls import path
from . import views

app_name = 'video_caption'

urlpatterns = [
    # Main tool page
    path('', views.caption_tool_home, name='home'),

    # Processing endpoints - FIXED: Use str instead of uuid for consistency
    path('status/<str:processing_id>/', views.processing_status, name='status'),
    path('retry/<str:processing_id>/', views.retry_processing, name='retry'),
    path('generate/', views.generate_captioned_video, name='generate'),

    # Queue and file management
    path('queue/', views.processing_queue, name='queue'),
    path('thumbnail/<str:processing_id>/', views.get_thumbnail, name='thumbnail'),
    path('download/<str:processing_id>/', views.download_result, name='download'),  # FIXED: Use processing_id
    path('serve/<int:file_id>/', views.serve_captioned_video, name='serve_video'),

    # API endpoints
    path('api/trials-left/', views.get_caption_tool_trials_left_api, name='api_trials_left'),
]