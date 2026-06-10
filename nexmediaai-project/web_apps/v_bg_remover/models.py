import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from core_apps.tools.models import Tool
User = get_user_model()

# Create your models here.
# models.py
class VideoProcessing(models.Model):
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('UPLOADING', 'Uploading to GPU'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    processing_id =  processing_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, null=True, blank=True)
    original_file = models.FileField(upload_to='temp_uploads/')
    result_file = models.FileField(upload_to='processed_videos/', null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.created_at}"

    class Meta:
        indexes = [
            models.Index(fields=['processing_id']),
            models.Index(fields=['user', 'created_at']),
        ]
    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.created_at}"

    @property
    def result_file_url(self):
        """Returns the URL for the result file if it exists"""
        if self.result_file:
            return self.result_file.url
        return None

    @property
    def result_file_name(self):
        """Returns just the filename portion"""
        if self.result_file:
            return os.path.basename(self.result_file.name)
        return None

    @property
    def original_file_name(self):
        """Returns just the filename portion"""
        return os.path.basename(self.original_file.name)