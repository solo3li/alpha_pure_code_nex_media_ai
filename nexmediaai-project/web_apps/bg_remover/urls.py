from django.urls import path
from . import views

urlpatterns = [
    path('get_trials_left/', views.get_trials_left, name='bg_get_trials'),
    path('upload/', views.upload_file, name='bg_upload'),
    path('remove_bg/', views.remove_bg, name='bg_process'),
    path('output/image/<int:file_id>/', views.serve_output_image, name='bg_output'),
    path('downloadProcessed/', views.download_processed, name='bg_download'),
    path('', views.home, name='bg_remover_home'),
]