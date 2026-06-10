# video_bg_remover/views.py
import json
import os
import uuid
import requests
import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.http import FileResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import FileToolData
from core_apps.subscriptions.models import Subscription
from core_apps.subscriptions.usage_manager import ToolUsageManager
from datetime import date
from urllib.parse import urljoin
from django.views.decorators.http import require_GET, require_POST
from web_apps.v_bg_remover.models import VideoProcessing
from celery import chain
from .tasks import upload_file_task, process_video_task
SIGNED_URL_SECRET_KEY = 'your-very-secret-key'
SIGNED_URL_EXPIRATION_SECONDS = 600  # 10 minutes
OUTPUT_DIR = os.path.join(settings.MEDIA_ROOT, 'processed_videos')
import hmac
import hashlib
import time
from django.utils.http import urlencode
from django.utils.encoding import force_bytes
from django.http import JsonResponse
from .models import VideoProcessing
logger = logging.getLogger(__name__)



# Use the correct Flask service URL
FLASK_SERVICE_URL = "http://149.36.1.159:5550"
TOOL_NAME = "video-bg-remover"
API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

# Make sure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

@login_required
def home(request):
    """Main view for the tool"""
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
            
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return render(request, 'v_bg_remover/index.html', {
            'trials_left': round(trials_left / 60, 1),
            'tool_name': TOOL_NAME,
            'static_url': '/static/video_bg_remover/'
        })
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return render(request, 'v_bg_remover/index.html', {
            'error': 'Tool not available'
        }, status=500)




@login_required
@csrf_exempt
@require_http_methods(["POST"])
def upload_file(request):
    """Initiate file processing workflow"""
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 0):
        return JsonResponse({
            'error': 'No valid subscription or trial',
            'subscribe_url': reverse('subscriptions:upgrade')
        }, status=403)
    
    file = request.FILES.get('file')
    if not file or not is_valid_video(file):
        return JsonResponse({'error': 'Invalid video file'}, status=400)
    
    # Check concurrent processing limit (max 2 videos at a time)
    tool = Tool.objects.get(name=TOOL_NAME)
    active_processes = VideoProcessing.objects.filter(
        user=request.user,
        tool=tool,
        status__in=['UPLOADED', 'UPLOADING', 'PROCESSING']
    ).count()
    
    if active_processes >= 2:
        return JsonResponse({
            'error': 'You can only process 2 videos at a time. Please wait for current processing to complete.',
            'active_count': active_processes
        }, status=429)
    
    try:
        # Generate unique processing ID
        processing_id = uuid.uuid4()
        
        # Store original file temporarily
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"{processing_id}_{file.name}")
        
        with open(temp_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Create processing record
        processing_record = VideoProcessing.objects.create(
            user=request.user,
            processing_id=processing_id,
            original_file=temp_path,
            status='UPLOADED',
            tool=tool,
        )
        
        # Start async processing chain
        chain(
            upload_file_task.s(processing_id),
            process_video_task.s(processing_id)
        ).apply_async()
        
        return JsonResponse({
            'processing_id': str(processing_id),
            'status_url': reverse('video_bg_status', args=[str(processing_id)]),
            'active_count': active_processes + 1
        })
        
    except Exception as e:
        logger.error(f"Upload initiation error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@require_GET
def get_thumbnail(request, processing_id):
    """
    Returns a default thumbnail image.
    """
    # Define the path to your default thumbnail within temp_uploads
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'video-thumbnail')
    default_thumbnail_path = os.path.join(temp_dir, 'video-thumb.png') # Assuming your default image is named 'video-thumb.png'

    # Ensure the default thumbnail file exists
    if not os.path.exists(default_thumbnail_path):
        # Handle the case where the default thumbnail doesn't exist.
        # You might want to log an error, raise an exception, or serve a generic fallback.
        # For this example, we'll return an empty response or a server error.
        # A more robust solution would involve ensuring this file is present during deployment.
        return FileResponse(open(os.path.join(settings.STATIC_ROOT, 'images/video-thumb.png'), 'rb'), content_type='image/png') # Fallback to static if default not found
        # Or you could raise an Http404 or HttpResponseServerError
        # from django.http import Http404
        # raise Http404("Default thumbnail not found.")


    return FileResponse(open(default_thumbnail_path, 'rb'), content_type='image/png')



def processing_queue(request):
    """Get user's processing queue"""
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
    tool = Tool.objects.filter(name=TOOL_NAME).first()
    queue = VideoProcessing.objects.filter(
        user=request.user,
        tool=tool
    ).order_by('-created_at')[:10]  # Last 10 items
    
    serialized_queue = []
   
    for item in queue:
        # Get the correct file ID for download/view
        file_id = None
        if item.status == 'COMPLETED' and item.result_file:
            # Extract the filename from the result_file path
            filename = os.path.basename(item.result_file.name)
            file_id = filename
            logger.info(f"Queue item {item.processing_id}: filename={filename}, file_id={file_id}")
        
        serialized_item = {
            'id': str(item.processing_id),
            'filename': item.original_file_name,
            'status': item.status,
            'progress': get_progress_value(item.status),
            'result_file_id': file_id,  # Use the filename as ID
            'thumbnail_url': f'/video-bg-remover/thumbnail/{item.processing_id}/',
            'created_at': item.created_at.isoformat(),
            'result_file_url': item.result_file_url if item.status == 'COMPLETED' else None,
            'download_url': f'/video-bg-remover/download/{file_id}/' if file_id else None,
            'view_url': f'/video-bg-remover/view/{file_id}/' if file_id else None
        }
        serialized_queue.append(serialized_item)
        logger.info(f"Serialized item: {serialized_item}")
    
    return JsonResponse(serialized_queue, safe=False)

def get_progress_value(status):
    """Map status to progress percentage"""
    return {
        'UPLOADED': 10,
        'UPLOADING': 30,
        'PROCESSING': 70,
        'COMPLETED': 100,
        'FAILED': 0
    }.get(status, 0)


def retry_processing(request, processing_id):
    """Retry a failed processing"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        record = VideoProcessing.objects.get(
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
        chain(
            upload_file_task.s(processing_id),
            process_video_task.s(processing_id)
        ).apply_async()
        
        return JsonResponse({'success': True})
        
    except VideoProcessing.DoesNotExist:
        return JsonResponse({'error': 'Invalid processing ID'}, status=404)

@require_GET
def download_result(request, file_id):
    """Download processed video file"""
    logger.info(f"Download request for file_id: {file_id}")
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        # Find the processing record by the result file name
        item = VideoProcessing.objects.get(
            result_file__endswith=file_id,  # Match the filename
            user=request.user,
            status='COMPLETED',
            tool=tool
        )
        
        logger.info(f"Found processing record: {item.processing_id}, result_file: {item.result_file}")
        
        if not item.result_file or not os.path.exists(item.result_file.path):
            logger.error(f"File not found: {item.result_file.path if item.result_file else 'None'}")
            return JsonResponse({'error': 'File not found'}, status=404)
            
        logger.info(f"Serving file: {item.result_file.path}")
        return FileResponse(
            open(item.result_file.path, 'rb'),
            as_attachment=True,
            filename=os.path.basename(item.result_file.name)
        )
    except VideoProcessing.DoesNotExist:
        logger.error(f"No VideoProcessing record found for file_id: {file_id}")
        return JsonResponse({'error': 'File not found'}, status=404)
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return JsonResponse({'error': 'Download failed'}, status=500)

@require_GET
def view_video(request, file_id):
    """View processed video file in browser"""
    logger.info(f"View request for file_id: {file_id}")
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        # Find the processing record by the result file name
        item = VideoProcessing.objects.get(
            result_file__endswith=file_id,  # Match the filename
            user=request.user,
            status='COMPLETED',
            tool=tool
        )
        
        logger.info(f"Found processing record: {item.processing_id}, result_file: {item.result_file}")
        
        if not item.result_file or not os.path.exists(item.result_file.path):
            logger.error(f"File not found: {item.result_file.path if item.result_file else 'None'}")
            return JsonResponse({'error': 'File not found'}, status=404)
            
        logger.info(f"Serving file for viewing: {item.result_file.path}")
        return FileResponse(
            open(item.result_file.path, 'rb'),
            content_type='video/mp4',
            as_attachment=False  # Display in browser
        )
    except VideoProcessing.DoesNotExist:
        logger.error(f"No VideoProcessing record found for file_id: {file_id}")
        return JsonResponse({'error': 'File not found'}, status=404)
    except Exception as e:
        logger.error(f"View error: {str(e)}")
        return JsonResponse({'error': 'View failed'}, status=500)
    
@require_GET
def processing_status(request, processing_id):
    """Get status of specific processing task"""
    try:
        item = VideoProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            tool=Tool.objects.get(name=TOOL_NAME)
        )
        
        # Get the correct file ID for download/view
        file_id = None
        if item.status == 'COMPLETED' and item.result_file:
            filename = os.path.basename(item.result_file.name)
            file_id = filename
        
        return JsonResponse({
            'status': item.status,
            'progress': get_progress_value(item.status),
            'result_file_id': file_id,
            'download_url': f'/video-bg-remover/download/{file_id}/' if file_id else None,
            'view_url': f'/video-bg-remover/view/{file_id}/' if file_id else None
        })
    except VideoProcessing.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    
@login_required
def check_status(request, processing_id):
    """Check processing status"""
    try:
        record = VideoProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            tool=Tool.objects.get(name=TOOL_NAME)
        )
        
        # Get the correct file ID for download/view
        file_id = None
        if record.status == 'COMPLETED' and record.result_file:
            filename = os.path.basename(record.result_file.name)
            file_id = filename
        
        return JsonResponse({
            'status': record.status,
            'result': {
                'file_id': file_id,
                'filename': record.result_file.name if record.result_file else None,
                'download_url': f'/video-bg-remover/download/{file_id}/' if file_id else None,
                'view_url': f'/video-bg-remover/view/{file_id}/' if file_id else None
            } if record.status == 'COMPLETED' else None,
            'error': record.error_message
        })
        
    except VideoProcessing.DoesNotExist:
        return JsonResponse({'error': 'Processing not found'}, status=404)

@login_required
def serve_output_video(request, file_id):
    """Serve processed video file"""
    file_data = get_object_or_404(FileToolData, id=file_id, user=request.user)
    
    try:
        # Ensure file exists
        if not os.path.exists(file_data.file_path):
            return JsonResponse({'error': 'Video file not found'}, status=404)
        
        # Stream the file
        response = FileResponse(open(file_data.file_path, 'rb'), content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename="{file_data.file_name}"'
        return response
    except Exception as e:
        logger.error(f"Video serve error: {str(e)}")
        return JsonResponse({'error': 'Failed to retrieve video'}, status=500)

def generate_signed_url(file_id, user_id, base_path):
    """Generate a signed URL that expires in N seconds"""
    expires = int(time.time()) + SIGNED_URL_EXPIRATION_SECONDS
    data = f"{file_id}:{user_id}:{expires}"
    signature = hmac.new(
        key=force_bytes(SIGNED_URL_SECRET_KEY),
        msg=force_bytes(data),
        digestmod=hashlib.sha256
    ).hexdigest()

    query_params = urlencode({
        'user': user_id,
        'expires': expires,
        'signature': signature
    })
    return f"{base_path}?{query_params}"

@csrf_exempt
@require_http_methods(["POST"])
def process_callback(request):
    """Receive processed file from Flask service"""
    try:
        # Verify API key
        if request.headers.get('X-Api-Key') != API_KEY:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        
        # Get file from request
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)
            
        file = request.FILES['file']
        user_id = request.headers.get('X-User-ID')
        
        if not user_id:
            return JsonResponse({'error': 'User ID required'}, status=400)
        
        # Save processed file
        unique_id = uuid.uuid4().hex
        filename = f"{user_id}_{unique_id}_{file.name}"
        file_path = os.path.join(OUTPUT_DIR, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Create file data record
        file_data = FileToolData.objects.create(
            user_id=user_id,
            file_name=filename,
            file_path=file_path,
            file_type='video/mp4'
        )
        
        return JsonResponse({
            'success': True,
            'file_id': file_data.id
        })
        
    except Exception as e:
        logger.error(f"Callback error: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def progress_stream(request):
    """Proxy progress updates from processing service"""
    try:
        # Forward request to Flask service
        response = requests.get(
            urljoin(FLASK_SERVICE_URL, '/progress'),
            headers={'X-Api-Key': API_KEY},
            stream=True
        )
        
        # Stream the response back to the client
        def generate():
            for chunk in response.iter_content(chunk_size=1024):
                yield chunk
                
        return StreamingHttpResponse(
            generate(),
            content_type='text/event-stream'
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Progress stream error: {str(e)}")
        return JsonResponse({'error': 'Progress service unavailable'}, status=503)



def is_valid_video(file):
    """Validate video file"""
    allowed_types = ['video/mp4', 'video/webm', 'video/quicktime']
    max_size = 100 * 1024 * 1024  # 100MB
    
    return (file.content_type in allowed_types and 
            file.size <= max_size and 
            file.name.lower().endswith(('.mp4', '.webm', '.mov')))

@login_required
def get_trials_left(request):
    """Endpoint to get remaining trial time for current user"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        # Get active processing count
        active_processes = VideoProcessing.objects.filter(
            user=request.user,
            tool=tool,
            status__in=['UPLOADED', 'UPLOADING', 'PROCESSING']
        ).count()
        
        return JsonResponse({
            'trials_left': trials_left,
            'max_input': 300,  # Maximum allowed video duration (5 minutes)
            'active_processes': active_processes,
            'max_concurrent': 2
        })
        
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return JsonResponse({
            'error': 'Tool not found',
            'trials_left': 0,
            'max_input': 300,
            'active_processes': 0,
            'max_concurrent': 2
        }, status=500)