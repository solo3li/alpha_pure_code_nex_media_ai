from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns, set_language
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from django.conf.urls.static import static

urlpatterns = [
    path('i18n/set-language/', set_language, name='set_language'),
    path(settings.ADMIN_URL, admin.site.urls),
    
    # API Documentation
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    # Authentication endpoints
    path("", include('core_apps.user_auth.urls')),
    path("", include('core_apps.home.urls')),
    path("", include('core_apps.user_profile.urls')),
    path("", include('core_apps.subscriptions.urls')),
    
    path('history/', include('core_apps.history.urls')),

    # Web apps endpoints
    path("bg-remover/", include('web_apps.bg_remover.urls')),
    path("video-bg-remover/", include('web_apps.v_bg_remover.urls')),
    path("video-caption/", include('web_apps.video_caption.urls')),
    path("img-to-text/", include('web_apps.img_to_txt.urls')),
    path("voice-to-text/", include('web_apps.voice_to_text.urls')),
    path("text-to-cartoon/", include('web_apps.text_to_cartoon.urls')),
    path("GPT/", include('web_apps.gpt.urls')),
    path("text-to-voice/", include('web_apps.text_to_voice.urls')),
    path("make-my-trip/", include('web_apps.make_my_trip.urls')),
 
    

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
admin.site.site_header = "NexMedia AI Admin"
admin.site.site_title = "NexMedia AI Admin Portal"
admin.site.index_title = "Welcome to NexMedia AI Admin Portal"