from django.contrib import admin

# Register your models here.
from .models import VideoProcessing


@admin.register(VideoProcessing)
class VideoProcessingAdmin(admin.ModelAdmin):
    list_display = ('user', 'processing_id', 'original_file', 'result_file', 'status', 'created_at', 'updated_at', 'tool')
     