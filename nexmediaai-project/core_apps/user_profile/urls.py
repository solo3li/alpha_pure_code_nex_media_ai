    # urls.py

from django.urls import path
from . import views


urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('upload_profile_image/', views.upload_profile_image, name='upload_profile_image'),
 
    ]


