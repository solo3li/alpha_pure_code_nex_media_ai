from django.urls import path
from . import views

app_name = 'history'

urlpatterns = [
    # Main history dashboard
    path('', views.index, name='index'),
    
    # History by tool name
    path('<str:tool_name>/', views.history_by_tool, name='history_by_tool'),
    
    # API endpoints
    path('api/get-history/', views.get_history, name='get_history'),
    path('api/get-text-history/', views.get_text_history, name='get_text_history'),
    path('api/get-make-my-trip-history/', views.get_make_my_trip_history, name='get_make_my_trip_history'),
    path('api/make-my-trip/getmydata/<int:trip_id>/', views.get_trip_data, name='get_trip_data'),
    
    # File serving
    path('serve-image/<str:filename>/', views.serve_image, name='serve_image'),
    
    # Trip viewing
    path('view-trip/<int:trip_id>/', views.view_trip, name='view_trip'),
    path('api/get-tts-history/', views.get_tts_history, name='get_tts_history')
]