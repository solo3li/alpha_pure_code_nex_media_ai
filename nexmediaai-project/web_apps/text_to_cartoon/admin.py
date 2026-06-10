from django.contrib import admin
from .models import CartoonProcessing
from django.utils.html import format_html
from django.urls import reverse


@admin.register(CartoonProcessing)
class CartoonProcessingAdmin(admin.ModelAdmin):
    list_display = (
        'processing_id_short',
        'user_email',
        'status',
        'created_at',
        'processing_time',
        'result_file_link',
        'error_status',
        'prompt'
    )
    list_filter = ('status', 'created_at', 'tool')
    search_fields = (
        'processing_id',
        'user__email',
        'user__username',
        'prompt',
        'error_message'
    )
    readonly_fields = (
        'processing_id',
        'created_at',
        'updated_at',
        'processing_time',
        'result_file_preview'
    )
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'processing_id',
                'user',
                'tool',
                'status',
                'processing_time'
            )
        }),
        ('Input/Output', {
            'fields': (
                'prompt',
                'result_image',
                'result_file_preview',
                'result_image_id'
            )
        }),
        ('Error Handling', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 25

    def processing_id_short(self, obj):
        return str(obj.processing_id)[:8]
    processing_id_short.short_description = 'Processing ID'
    processing_id_short.admin_order_field = 'processing_id'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'

    def processing_time(self, obj):
        if obj.created_at and obj.updated_at:
            delta = obj.updated_at - obj.created_at
            return f"{delta.total_seconds():.1f}s"
        return "-"
    processing_time.short_description = 'Processing Time'

    def result_file_link(self, obj):
        if obj.status == 'COMPLETED' and obj.result_image:
            url = reverse('admin:text_to_cartoon_cartoonprocessing_download', args=[obj.pk])
            return format_html('<a href="{}" download>Download</a>', url)
        return "-"
    result_file_link.short_description = 'Result File'

    def result_file_preview(self, obj):
        if obj.status == 'COMPLETED' and obj.result_image:
            if obj.result_image.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return format_html(
                    '<img src="{}" style="max-height: 200px; max-width: 100%;" />',
                    obj.result_image.url
                )
            return format_html(
                '<a href="{}" download>Download File</a>',
                obj.result_image.url
            )
        return "-"
    result_file_preview.short_description = 'Preview'
    result_file_preview.allow_tags = True

    def error_status(self, obj):
        if obj.error_message:
            return format_html('<span style="color: red;">ERROR</span>')
        return "-"
    error_status.short_description = 'Error'
    error_status.allow_tags = True

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/download/',
                self.admin_site.admin_view(self.download_result),
                name='text_to_cartoon_cartoonprocessing_download'
            ),
        ]
        return custom_urls + urls

    def download_result(self, request, object_id, *args, **kwargs):
        from django.http import FileResponse
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        if not request.user.has_perm('text_to_cartoon.view_cartoonprocessing'):
            raise PermissionDenied

        obj = self.get_object(request, object_id)
        if not obj or not obj.result_image:
            raise Http404('File not found')

        return FileResponse(obj.result_image.open('rb'), as_attachment=True)
