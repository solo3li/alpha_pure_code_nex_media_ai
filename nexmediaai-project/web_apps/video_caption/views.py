# video_caption/views.py (Cleaned Version)
import json
import os
import uuid
import requests
import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
from django.core.files.base import ContentFile
from celery import chain

from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import FileToolData
from core_apps.subscriptions.models import Subscription
from core_apps.subscriptions.usage_manager import ToolUsageManager
from datetime import date
from loguru import logger
from .models import VideoCaptionProcessing
from .tasks import upload_file_task

# Configuration
TOOL_NAME = "video-caption"
DEFAULT_OUTPUT_DIR_NAME = 'processed_captioned_videos'
OUTPUT_DIR = os.path.join(settings.MEDIA_ROOT, DEFAULT_OUTPUT_DIR_NAME)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@login_required
def caption_tool_home(request):
    """Main view for the video captioning tool"""
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return render(request, 'video_caption/index.html', {
            'trials_left': round(trials_left / 60, 1),
            'tool_name': TOOL_NAME,
            'static_url': '/static/video-caption/'
        })
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return render(request, 'video_caption/index.html', {
            'error': 'Tool not available'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_captioned_video(request):
    """Initiate video caption processing workflow - cleaned parameters"""
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 0):
        return JsonResponse({
            'error': 'No valid subscription or trial',
        }, status=403)
    
    video_file = request.FILES.get('video')
    if not video_file:
        return JsonResponse({'error': 'No video file provided'}, status=400)
    
    is_valid, msg = is_valid_video_file(video_file)
    if not is_valid:
        return JsonResponse({'error': msg}, status=400)
    
    # Check concurrent processing limit (max 2 videos at a time)
    tool = Tool.objects.get(name=TOOL_NAME)
    active_processes = VideoCaptionProcessing.objects.filter(
        user=request.user,
        tool=tool,
        status__in=['UPLOADED', 'UPLOADING', 'PROCESSING']
    ).count()
    
    if active_processes >= 2:
        return JsonResponse({
            'error': 'You can only process 2 videos at a time. Please wait for current processing to complete.',
            'active_count': active_processes
        }, status=429)
    
    # Get only the essential caption parameters that are actually used by the API
    target_language = request.POST.get('language', 'en')
    font_family = request.POST.get('fontFamily', 'arfonts-arial-bold.ttf')  # Changed to match HTML
    font_size_str = request.POST.get('fontSize', '24')
    font_color = request.POST.get('fontColor', 'white')
    
    try:
        font_size = int(font_size_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid font size value'}, status=400)
    
    try:
        # Generate unique processing ID
        processing_id = uuid.uuid4()
        
        # Create processing record with only the parameters we actually use
        processing_record = VideoCaptionProcessing.objects.create(
            user=request.user,
            processing_id=processing_id,
            target_language=target_language,
            font_family=font_family,
            font_size=font_size,
            font_color=font_color,
            status='UPLOADED',
            tool=tool,
        )
        
        # Save file to the record using Django's FileField
        file_name = f"{processing_id}_{video_file.name}"
        processing_record.original_file.save(
            file_name,
            ContentFile(video_file.read()),
            save=True
        )
        
        # Start async processing
        upload_file_task.apply_async(args=[processing_id])
        
        return JsonResponse({
            'processing_id': str(processing_id),
            'active_count': active_processes + 1
        })
        
    except Exception as e:
        logger.error(f"Caption generation initiation error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@require_GET
def processing_queue(request):
    """Get user's processing queue"""
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
        
    tool = Tool.objects.filter(name=TOOL_NAME).first()
    if not tool:
        return JsonResponse([], safe=False)
        
    queue = VideoCaptionProcessing.objects.filter(
        user=request.user,
        tool=tool
    ).order_by('-created_at')[:10]  # Last 10 items
    
    serialized_queue = []
    for item in queue:
        # Get original filename
        original_filename = "unknown"
        if item.original_file:
            original_filename = os.path.basename(item.original_file.name)
        
        # Get result file URL
        result_file_url = None
        if item.status == 'COMPLETED' and item.result_file:
            result_file_url = f'/video-caption/download/{item.processing_id}/'
        
        serialized_item = {
            'id': str(item.processing_id),
            'filename': original_filename,
            'status': item.status,
            'progress': get_progress_value(item.status),
            'result_file_id': str(item.processing_id) if item.result_file else None,
            'video_data_id': str(item.processing_id) if item.status == 'COMPLETED' else None,
            'thumbnail_url': f'/video-caption/thumbnail/{item.processing_id}/',
            'created_at': item.created_at.isoformat(),
            'result_file_url': result_file_url,
            'error_message': item.error_message if item.status == 'FAILED' else None,
            'caption_params': {
                'language': item.target_language,
                'font_family': item.font_family,
                'font_size': item.font_size,
                'font_color': item.font_color,
            }
        }
        serialized_queue.append(serialized_item)
    
    return JsonResponse(serialized_queue, safe=False)

def get_progress_value(status):
    """Map status to progress percentage"""
    return {
        'UPLOADED': 10,
        'PROCESSING': 70,
        'COMPLETED': 100,
        'FAILED': 0
    }.get(status, 0)

@require_GET
def get_thumbnail(request, processing_id):
    """Returns a default thumbnail image."""
    try:
        # Try to get the default thumbnail from media directory
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'video-thumbnail')
        default_thumbnail_path = os.path.join(temp_dir, 'video-thumb.png')

        if os.path.exists(default_thumbnail_path):
            return FileResponse(
                open(default_thumbnail_path, 'rb'), 
                content_type='image/png'
            )
        
        # Fallback to static directory
        static_thumbnail_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'images', 'video-thumb.png')
        if os.path.exists(static_thumbnail_path):
            return FileResponse(
                open(static_thumbnail_path, 'rb'), 
                content_type='image/png'
            )
        
        # If no thumbnail found, return a simple response
        return JsonResponse({'error': 'Thumbnail not available'}, status=404)
        
    except Exception as e:
        logger.error(f"Error serving thumbnail for {processing_id}: {str(e)}")
        return JsonResponse({'error': 'Thumbnail not available'}, status=404)

@require_GET
def processing_status(request, processing_id):
    """Get status of specific processing task"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        item = VideoCaptionProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            tool=tool
        )
        
        # Use processing_id for download URL
        result_file_url = None
        if item.status == 'COMPLETED' and item.result_file:
            result_file_url = f'/video-caption/download/{item.processing_id}/'
        
        return JsonResponse({
            'status': item.status,
            'progress': get_progress_value(item.status),
            'result_file_id': str(item.processing_id) if item.result_file else None,
            'video_data_id': str(item.processing_id) if item.status == 'COMPLETED' else None,
            'result_file_url': result_file_url,
            'error': item.error_message if item.status == 'FAILED' else None
        })
    except VideoCaptionProcessing.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Tool not found'}, status=404)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def retry_processing(request, processing_id):
    """Retry a failed processing"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        record = VideoCaptionProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            status='FAILED',
            tool=tool
        )
        
        # Reset record
        record.status = 'UPLOADED'
        record.error_message = None
        record.save()
        
        # Trigger processing again
        upload_file_task.delay(str(processing_id))
        
        return JsonResponse({'success': True})
        
    except VideoCaptionProcessing.DoesNotExist:
        return JsonResponse({'error': 'Invalid processing ID or not failed'}, status=404)
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Tool not found'}, status=404)

@require_GET
def download_result(request, processing_id):
    """Download processed captioned video file"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        item = VideoCaptionProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            status='COMPLETED',
            tool=tool
        )
        
        if not item.result_file:
            return JsonResponse({'error': 'No result file available'}, status=404)
        
        if not os.path.exists(item.result_file.path):
            logger.error(f"Result file not found on disk: {item.result_file.path}")
            return JsonResponse({'error': 'File not found on server'}, status=404)
        
        # Get original filename for download
        original_name = "captioned_video.mp4"
        if item.original_file:
            base_name = os.path.splitext(os.path.basename(item.original_file.name))[0]
            original_name = f"captioned_{base_name}.mp4"
        
        response = FileResponse(
            open(item.result_file.path, 'rb'), 
            as_attachment=True,
            filename=original_name,
            content_type='video/mp4'
        )
        
        logger.info(f"Serving captioned video download for processing_id: {processing_id}")
        return response
        
    except VideoCaptionProcessing.DoesNotExist:
        return JsonResponse({'error': 'File not found'}, status=404)
    except Tool.DoesNotExist:
        return JsonResponse({'error': 'Tool not found'}, status=404)
    except Exception as e:
        logger.error(f"Error downloading result for {processing_id}: {str(e)}")
        return JsonResponse({'error': 'Failed to download file'}, status=500)
        
@login_required
def get_caption_tool_trials_left_api(request):
    """Get remaining trial time for video caption tool"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        # Get active processing count
        active_processes = VideoCaptionProcessing.objects.filter(
            user=request.user,
            tool=tool,
            status__in=['UPLOADED', 'UPLOADING', 'PROCESSING']
        ).count()
        
        return JsonResponse({
            'trials_left': trials_left,
            'max_input': 900,  # Maximum allowed video duration (15 minutes)
            'active_processes': active_processes,
            'max_concurrent': 2
        })
        
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return JsonResponse({
            'error': 'Tool not found',
            'trials_left': 0,
            'max_input': 900,
            'active_processes': 0,
            'max_concurrent': 2
        }, status=500)
    except Exception as e:
        logger.error(f"Error in get_caption_tool_trials_left_api: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Could not retrieve trial information'}, status=500)



def is_valid_video_file(file_obj):
    """Validate video file type and size"""
    allowed_types = ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-matroska', 'video/avi']
    max_size = 500 * 1024 * 1024  # 100MB
    
    if file_obj.content_type not in allowed_types:
        return False, f"Invalid file type: {file_obj.content_type}. Allowed: MP4, WebM, MOV, MKV, AVI."
    
    if file_obj.size > max_size:
        return False, f"File too large: {file_obj.size // (1024*1024)}MB. Maximum size is {max_size // (1024*1024)}MB."
    
    return True, "Valid file."

@login_required
def serve_captioned_video(request, file_id):
    """Serves the processed and captioned video file to the user for download"""
    try:
        file_data = get_object_or_404(FileToolData, id=file_id, user=request.user)
        if not os.path.exists(file_data.file_path):
            logger.error(f"File not found: {file_data.file_path} for file_id: {file_id}")
            return JsonResponse({'error': 'Video file not found on server'}, status=404)
        
        response = FileResponse(open(file_data.file_path, 'rb'), content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename="{file_data.file_name}"'
        logger.info(f"Serving captioned video: {file_data.file_name} to user {request.user.id}")
        return response
    except Exception as e:
        logger.error(f"Error serving captioned video ID {file_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to retrieve video'}, status=500)