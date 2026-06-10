from django.urls import path
from . import views

app_name = 'trip_planner'

urlpatterns = [
    path('', views.home, name='home'),
    path('results/', views.results, name='results'),
    path('getUserInfo/', views.get_user_info, name='get_user_info'),
    path('get_trials_left/', views.get_trials_left_endpoint, name='get_trials_left'),
    path('getmydata/', views.get_my_data, name='get_my_data'),
    path('subscribe/', views.subscribe, name='subscribe'),
]