# text_to_cartoon/models.py
import os
from django.db import models
from django.contrib.auth import get_user_model
from core_apps.tools.models import Tool

User = get_user_model()

class CartoonProcessing(models.Model):
    STATUS_CHOICES = [
        ('UPLOADED', 'Uploaded'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    processing_id = models.UUIDField(unique=True, db_index=True)
    
    # Processing settings
    prompt = models.TextField(help_text="Text prompt for cartoon generation")
    
    # Status and results
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPLOADED')
    result_image = models.FileField(upload_to='cartoon_results/', null=True, blank=True)
    result_image_id = models.IntegerField(null=True, blank=True, help_text="Reference to FileToolData ID")
    
    # Error handling
    error_message = models.CharField(max_length=500, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cartoon_processing'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['processing_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"CartoonProcessing {self.processing_id} - {self.user.username} - {self.status}"
    
    @property
    def result_file_name(self):
        """Get the result filename"""
        return f"cartoon_{self.processing_id}.png"
    
    @property
    def result_file_url(self):
        """Get URL for downloading the result"""
        if self.status == 'COMPLETED' and self.result_image:
            return self.result_image.url
        return None
    
    def delete(self, *args, **kwargs):
        """Override delete to clean up files"""
        if self.result_image:
            try:
                if os.path.isfile(self.result_image.path):
                    os.remove(self.result_image.path)
            except:
                pass
        super().delete(*args, **kwargs)