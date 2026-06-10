from django.urls import path, re_path
from . import views


urlpatterns = [
    path('', views.home, name='video_bg_remover_home'),
    path('get_trials_left/', views.get_trials_left, name='video_bg_get_trials'),
    path('upload/', views.upload_file, name='video_bg_upload'),
    path('progress/', views.progress_stream, name='video_bg_progress'),
    path('output/video/<int:file_id>/', views.serve_output_video, name='video_bg_output'),
    path('callback/', views.process_callback, name='video_bg_callback'),
    
    # New URLs for queue system
    path('processing-queue/', views.processing_queue, name='video_bg_queue'),
    path('retry/<uuid:processing_id>/', views.retry_processing, name='video_bg_retry'),

    re_path(r'^status/(?P<processing_id>[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12})/$', 
        views.processing_status, 
        name='video_bg_status'),
    path('download/<str:file_id>/', views.download_result, name='video_bg_download'),
    path('view/<str:file_id>/', views.view_video, name='video_bg_view'),
    path('thumbnail/<uuid:processing_id>/', views.get_thumbnail, name='video_bg_thumbnail'),
]
