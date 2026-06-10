# tool_data/models.py
import uuid
from django.contrib.auth import get_user_model
User = get_user_model()
from django.db import models
from django.utils import timezone
class TextToolData(models.Model):
    content = models.TextField()

    def __str__(self):
        return f"TextData {self.id}"

class FileToolData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now, editable=True)  # ✅ added field

    def __str__(self):
        return self.file_name

class MapToolData(models.Model):
    place = models.CharField(max_length=255)
    thumbnail = models.TextField()
    data = models.JSONField()
    token = models.UUIDField(default=uuid.uuid4, null=True)


    def __str__(self):
        return self.place
