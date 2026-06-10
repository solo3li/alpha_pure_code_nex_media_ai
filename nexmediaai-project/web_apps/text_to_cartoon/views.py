# text_to_cartoon/views.py
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.conf import settings
from django.urls import reverse
from loguru import logger
import json
import os
import uuid
from celery import chain

from core_apps.subscriptions.models import Subscription
from core_apps.tool_data.models import FileToolData
from core_apps.tools.models import ToolUsage, Tool, ToolUsageHistory
from core_apps.subscriptions.usage_manager import ToolUsageManager
from .models import CartoonProcessing
from .tasks import process_cartoon_task

TOOL_NAME = "text-to-cartoon"

@login_required
def home(request):
    """Main view for the text-to-cartoon tool"""
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return render(request, 'text_to_cartoon/index.html', {
            'number_of_trials': trials_left,
            'tool_name': TOOL_NAME,
        })
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return render(request, 'text_to_cartoon/index.html', {
            'error': 'Tool not available'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def upload_prompt(request):
    """Initialize cartoon processing with prompt"""
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 0):
        return JsonResponse({
            'show': 'No-sub-no-Trial',
            'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        }, status=403)

    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    if not prompt:
        return JsonResponse({"error": "Prompt is required"}, status=400)

    if len(prompt) > 500:
        return JsonResponse({"error": "Prompt too long (max 500 characters)"}, status=400)

    try:
        processing_id = uuid.uuid4()
        tool = Tool.objects.get(name=TOOL_NAME)

        processing_record = CartoonProcessing.objects.create(
            user=request.user,
            processing_id=processing_id,
            status='UPLOADED',
            tool=tool,
            prompt=prompt
        )

        remaining_trials = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        if remaining_trials <= 0:
            processing_record.delete()  # Clean up record
            return JsonResponse({
                "error": "No trials remaining",
                "trials": 0,
            }, status=403)

        return JsonResponse({
            'processing_id': str(processing_id),
            'prompt': prompt,
        })

    except Exception as e:
        logger.error(f"[UPLOAD] Upload initiation error: {str(e)}", exc_info=True)

        if 'processing_record' in locals():
            processing_record.status = 'FAILED'
            processing_record.save()
            logger.info(f"[UPLOAD] Marked record as FAILED: ID={processing_record.id}")

        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_cartoon(request):
    """Start cartoon processing"""
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 0):
        return JsonResponse({
            'show': 'No-sub-no-Trial',
            'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        }, status=403)

    try:
        data = json.loads(request.body)
        processing_id = data.get('processing_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    
    if not processing_id:
        return JsonResponse({"error": "Processing ID required"}, status=400)
    
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        record = CartoonProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            tool=tool
        )
        
        # Start async processing
        process_cartoon_task.apply_async(args=[str(processing_id)])
        
        return JsonResponse({
            'success': True,
            'processing_id': str(processing_id),
        })
        
    except CartoonProcessing.DoesNotExist:
        return JsonResponse({'error': 'Invalid processing ID'}, status=404)
    except Exception as e:
        logger.error(f"Processing initiation error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@require_GET
def processing_status(request, processing_id):
    """Get status of specific processing task"""
    try:
        item = CartoonProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
            tool=Tool.objects.get(name=TOOL_NAME)
        )
        
        response_data = {
            'status': item.status,
            'progress': get_progress_value(item.status),
            'error': item.error_message
        }
        
        if item.status == 'COMPLETED':
            response_data.update({
                'image_url': item.result_file_url,
                'image_data_id': item.result_image_id
            })
            
        return JsonResponse(response_data)
        
    except CartoonProcessing.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

def processing_queue(request):
    """Get user's processing queue"""
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
        
    tool = Tool.objects.filter(name=TOOL_NAME).first()
    queue = CartoonProcessing.objects.filter(
        user=request.user,
        tool=tool
    ).order_by('-created_at')[:10]  # Last 10 items
    
    serialized_queue = []
    for item in queue:
        serialized_item = {
            'id': str(item.processing_id),
            'filename': f"Prompt: {item.prompt[:15]}..." if len(item.prompt) > 15 else f"Cartoon: {item.prompt}",
            'status': item.status,
            'progress': get_progress_value(item.status),
            'prompt': item.prompt,
            'created_at': item.created_at.isoformat(),
            'result_image_url': f"/text-to-cartoon/result/{item.result_image_id}/" if item.status == 'COMPLETED' and item.result_image_id else None,
            'image_data_id': item.result_image_id if item.status == 'COMPLETED' else None,
            'error': item.error_message if item.status == 'FAILED' else None
        }
        serialized_queue.append(serialized_item)
    
    return JsonResponse(serialized_queue, safe=False)

def retry_processing(request, processing_id):
    """Retry a failed processing"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        record = CartoonProcessing.objects.get(
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
        process_cartoon_task.apply_async(args=[str(processing_id)])
        
        return JsonResponse({'success': True})
        
    except CartoonProcessing.DoesNotExist:
        return JsonResponse({'error': 'Invalid processing ID'}, status=404)

@login_required
def get_image_result(request, image_data_id):
    """Get cartoon image result"""
    try:
        file_data = get_object_or_404(FileToolData, id=image_data_id)
        
        # Verify user has access through processing record
        processing_record = CartoonProcessing.objects.filter(
            user=request.user,
            result_image_id=image_data_id,
            tool=Tool.objects.get(name=TOOL_NAME)
        ).first()
        
        if not processing_record:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if file exists
        if not os.path.exists(file_data.file_path):
            return JsonResponse({'error': 'File not found on disk'}, status=404)
            
        # Read and return the image file
        try:
            with open(file_data.file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='image/png')
                
                # Add headers for proper handling
                response['Content-Disposition'] = f'inline; filename="{file_data.file_name}"'
                response['Cache-Control'] = 'max-age=3600'  # Cache for 1 hour
                
                return response
                
        except IOError as e:
            logger.error(f"Error reading file {file_data.file_path}: {str(e)}")
            return JsonResponse({'error': 'Error reading image file'}, status=500)
        
    except FileToolData.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return JsonResponse({'error': 'Tool not found'}, status=500)
    except Exception as e:
        logger.error(f"Unexpected error in get_image_result: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

def get_progress_value(status):
    """Map status to progress percentage"""
    return {
        'UPLOADED': 10,
        'PROCESSING': 50,
        'COMPLETED': 100,
        'FAILED': 0
    }.get(status, 0)

@login_required
def get_trials_left_api(request):
    """Endpoint to get remaining trials for current user"""
    try:
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return JsonResponse({
            'trials_left': trials_left,
        })
        
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return JsonResponse({
            'error': 'Tool not found',
            'trials_left': 0,
        }, status=500)