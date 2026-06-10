from django.contrib import admin
from .models import VoiceProcessing

@admin.register(VoiceProcessing)
class VoiceProcessingAdmin(admin.ModelAdmin):
    list_display = [field.name for field in VoiceProcessing._meta.fields]
    search_fields = [field.name for field in VoiceProcessing._meta.fields if field.get_internal_type() in ('CharField', 'TextField')]