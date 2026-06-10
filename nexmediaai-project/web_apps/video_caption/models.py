# video_caption/models.py
import os
from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth import get_user_model

from core_apps.tools.models import Tool
User = get_user_model()
class VideoCaptionProcessing(models.Model):
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('UPLOADING', 'Uploading'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    processing_id = models.UUIDField(unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    
    # File fields
    original_file = models.FileField(upload_to='temp_caption_uploads/')
    result_file = models.FileField(upload_to='processed_captioned_videos/', null=True, blank=True)
    
    # Caption parameters
    target_language = models.CharField(max_length=10, default='en')
    font_family = models.CharField(max_length=100, default='Arial.ttf')
    font_size = models.IntegerField(default=24)
    font_color = models.CharField(max_length=50, default='white')
    
    # Processing info
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    error_message = models.TextField(null=True, blank=True)
    video_duration = models.IntegerField(default=0, help_text="Duration in seconds")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['processing_id']),
        ]
    
    def __str__(self):
        return f"Caption Processing {self.processing_id} - {self.status}"
    
    @property
    def original_file_name(self):
        """Get the original filename without path"""
        if self.original_file:
            return os.path.basename(self.original_file.name)
        return None
    
    @property
    def result_file_name(self):
        """Get the result filename without path"""
        if self.result_file:
            return os.path.basename(self.result_file.name)
        return None
    
    @property
    def result_file_url(self):
        """Get the URL for downloading the result file"""
        if self.result_file and self.status == 'COMPLETED':
            return f'/video-caption/download/{self.result_file_name}/'
        return None