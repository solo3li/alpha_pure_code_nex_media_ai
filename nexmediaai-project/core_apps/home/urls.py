from django.urls import path
from . import views

app_name = 'home'


urlpatterns = [
    path('home/', views.home_view, name='home'),
    path('', views.home_view, name='home'),
    path('add-phone-number/', views.add_phone_number, name='add_phone_number'),
    path('contact/', views.contact_view, name='contact'),
    path('api/plans/', views.PlansAPIView.as_view(), name='get_plans'),
    path('profile/image/<uuid:user_id>/', views.serve_profile_image, name='serve_profile_image'),
    path('terms/', views.terms_view, name='terms'),
]
