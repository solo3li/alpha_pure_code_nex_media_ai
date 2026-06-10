from django.contrib import admin
from .models import TextToolData, FileToolData, MapToolData

@admin.register(TextToolData)
class TextToolDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'content')

 

@admin.register(FileToolData)
class FileToolDataAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'user', 'created_at')
    fields = ('user', 'file_name', 'file_path', 'created_at')  # 👈 make sure it's here


@admin.register(MapToolData)
class MapToolDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'place', 'thumbnail', 'token')  # Added 'thumbnail' and 'token' fields
