from django.contrib import admin

# Register your models here.
from .models import VideoCaptionProcessing


@admin.register(VideoCaptionProcessing)
class VideoCaptionProcessingAdmin(admin.ModelAdmin):
    list_display = (
        'processing_id', 'user', 'tool', 'status', 'created_at', 'updated_at',
        'original_file_name', 'result_file_name', 'target_language', 'font_size', 'font_color', 'font_family', 'video_duration'
    )
    search_fields = ('processing_id', 'user__username', 'tool__name')
    list_filter = ('status', 'created_at', 'updated_at')
    readonly_fields = ('processing_id', 'created_at', 'updated_at')

    def original_file_name(self, obj):
        return obj.original_file_name

    def result_file_name(self, obj):
        return obj.result_file_name

    original_file_name.short_description = "Original File Name"
    result_file_name.short_description = "Result File Name"



