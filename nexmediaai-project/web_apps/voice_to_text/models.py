# voice_to_text/models.py
import os
from django.db import models
from django.contrib.auth import get_user_model
from core_apps.tools.models import Tool

User = get_user_model()

class VoiceProcessing(models.Model):
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('UPLOADING', 'Uploading'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('zh', 'Chinese'),
        ('ar', 'Arabic'),
        ('hi', 'Hindi'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    processing_id = models.UUIDField(unique=True, db_index=True)
    
    # File information
    original_file = models.FileField(upload_to='temp_audio_uploads/', null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True, help_text="Duration in seconds")
    
    # Processing settings
    target_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')
    
    # Status and results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    result_text = models.TextField(null=True, blank=True)
    result_text_id = models.IntegerField(null=True, blank=True, help_text="Reference to TextToolData ID")
    
    # Error handling
    error_message = models.CharField(max_length=500, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'voice_processing'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['processing_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"VoiceProcessing {self.processing_id} - {self.user.username} - {self.status}"
    
    @property
    def original_file_name(self):
        """Get the original filename"""
        if self.original_file:
            return os.path.basename(self.original_file.name)
        return None
    
    @property
    def result_file_name(self):
        """Get the result filename (for consistency with other apps)"""
        return f"transcription_{self.processing_id}.txt"
    
    @property
    def result_file_url(self):
        """Get URL for downloading the result"""
        if self.status == 'COMPLETED' and self.result_text_id:
            from django.urls import reverse
            return reverse('voice_to_text_result', args=[self.result_text_id])
        return None
    
    def delete(self, *args, **kwargs):
        """Override delete to clean up files"""
        if self.original_file:
            try:
                if os.path.isfile(self.original_file.path):
                    os.remove(self.original_file.path)
            except:
                pass
        super().delete(*args, **kwargs)