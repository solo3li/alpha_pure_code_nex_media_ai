import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from loguru import logger
import requests
import os
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import TextToolData
from core_apps.subscriptions.usage_manager import ToolUsageManager
from datetime import datetime

FLASK_SERVICE_URL = getattr(settings, 'FLASK_SERVICE_URL', 'http://img_to_txt:5004')
API_KEY = getattr(settings, 'FLASK_API_KEY', 'GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf')

@login_required
def home(request):
    tool_name = "img-to-txt"
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        number_of_trials = ToolUsageManager.get_trials_left(request.user, tool_name)
    except Exception as err:
        print(f"Database Error: {err}")
        number_of_trials = "Error fetching trials"

    return render(request, 'img_to_txt/index.html', {'number_of_trials': number_of_trials})

@login_required
def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        file = request.FILES['file']
        tool_name = "img-to-txt"
        
        # Check trial availability
        trial_available = ToolUsageManager.is_trial_available(request.user, tool_name, 1)
        if not trial_available:
            return JsonResponse({
                'show': 'No-sub-no-Trial',
                'subscribe_url': '/subscribe/',
                'trials': ToolUsageManager.get_trials_left(request.user, tool_name)
            })

        try:
            # Send file to Flask service
            response = requests.post(
                f"{FLASK_SERVICE_URL}/upload",
                files={'image': (file.name, file)},
                headers={
                    'X-User-ID': str(request.user.id),
                    'X-Api-Key': API_KEY
                },
                timeout=1000
            )
            response.raise_for_status()
            data = response.json()
            
            return JsonResponse({
                'file_path': f"/media/uploads/{data['filename']}",
                'filename': data['filename']
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e),
                                 "response":data}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def generate_caption(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    tool_name = "img-to-txt"
    
    try:
        # Validate and parse JSON data
        try:
            data = json.loads(request.body)
            filename = data.get('file_path')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except AttributeError:
            return JsonResponse({'error': 'Invalid request format'}, status=400)

        # Validate filename exists and is not empty
        if not filename or not isinstance(filename, str) or not filename.strip():
            return JsonResponse({
                'error': 'Valid filename is required',
                'received_data': data
            }, status=400)

        # Debug logging
        logger.info(f"Caption generation request from user {request.user.id} for file: {filename}")
        
        # Check trial availability
        trial_available = ToolUsageManager.is_trial_available(request.user, tool_name, 1)
        remaining_trials = ToolUsageManager.get_trials_left(request.user, tool_name)
        if not trial_available:
            return JsonResponse({
                'show': 'No-sub-no-Trial',
                'subscribe_url': '/subscribe/',
                'trials': remaining_trials
            }, status=403)

        # Prepare Flask service request
        flask_url = f"{FLASK_SERVICE_URL}/generate"
        headers = {
            'X-User-ID': str(request.user.id),
            'X-Api-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {'filename': filename.strip()}

        logger.debug(f"Sending to Flask service: URL={flask_url}, Headers={headers}")

        # Send request to Flask service with timeout
        try:
            response = requests.post(
                flask_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.Timeout:
            logger.error("Flask service timeout")
            return JsonResponse({'error': 'Caption generation service timeout'}, status=504)
        except requests.exceptions.RequestException as e:
            logger.error(f"Flask service error: {str(e)}")
            return JsonResponse({
                'error': 'Caption generation service unavailable',
                'details': str(e)
            }, status=503)

        # Validate Flask response
        if not isinstance(result, dict) or 'caption' not in result:
            logger.error(f"Invalid response format from Flask: {result}")
            return JsonResponse({'error': 'Invalid response from caption service'}, status=502)

        # Save caption and usage
        try:
            text_data = TextToolData.objects.create(
                content=result['caption']
            )
            
            tool = Tool.objects.get(name=tool_name)
            
            ToolUsageHistory.objects.create(
                user=request.user,
                tool=tool,
                additional_data_id=text_data.id
            )
            
            ToolUsageManager.decrement_trials(request.user, tool_name, 1)
            
            logger.info(f"Successfully generated caption for user {request.user.id}")
            return JsonResponse({'caption': result['caption']})
            
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            return JsonResponse({
                'error': 'Failed to save caption',
                'caption': result['caption']  # Still return the caption even if save failed
            }, status=201)

    except Exception as e:
        logger.exception("Unexpected error in generate_caption")
        return JsonResponse({
            'error': 'Internal server error',
            'details': str(e)
        }, status=500)
    
@login_required
def get_trials_left_api(request):
    """Preserved endpoint for frontend"""
    trials_left = ToolUsageManager.get_trials_left(request.user, "img-to-txt")
    return JsonResponse({'trials_left': trials_left})