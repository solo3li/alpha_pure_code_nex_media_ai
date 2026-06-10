# voice_to_text/views.py
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET
from django.conf import settings
from loguru import logger
import requests
import os
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip

from core_apps.subscriptions.models import Subscription
from core_apps.tool_data.models import TextToolData
from core_apps.tools.models import ToolUsage, Tool, ToolUsageHistory
from core_apps.subscriptions.usage_manager import ToolUsageManager
from .models import VoiceProcessing

TOOL_NAME = "voice-to-text"

FLASK_API_URL = os.getenv('FLASK_API_URL', 'http://voice_to_text:5005')  # Your Flask API URL

@login_required
def home(request):
    """Main view for the voice-to-text tool"""
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        tool = Tool.objects.get(name=TOOL_NAME)
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return render(request, 'voice_to_text/index.html', {
            'number_of_trials': round(trials_left / 60, 1),
            'tool_name': TOOL_NAME,
        })
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return render(request, 'voice_to_text/index.html', {
            'error': 'Tool not available'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def process_audio(request):
    """Process audio directly with OpenAI API via Flask"""
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 0):
        return JsonResponse({
            'show': 'No-sub-no-Trial',
            'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        }, status=403)

    if 'audio' not in request.FILES:
        return JsonResponse({"error": "No media file provided"}, status=400)

    file = request.FILES['audio']
    language = request.POST.get('target', 'en')
    should_translate = request.POST.get('translate', 'false')  # Get translate flag

    if not is_valid_audio(file):
        return JsonResponse({'error': 'Invalid audio file'}, status=400)

    try:
        # Get duration for trial check
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            clip = AudioFileClip(temp_path)
        except Exception:
            clip = VideoFileClip(temp_path)
        
        duration = int(clip.duration)
        clip.close()

        # Check remaining trials
        remaining_trials = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        if duration > remaining_trials:
            os.unlink(temp_path)
            return JsonResponse({
                "error": f"File too long. Duration: {duration}s, Remaining: {int(remaining_trials)}s",
                "trials": int(remaining_trials),
            }, status=403)

        # Send file to Flask API for processing with language parameter
        file.seek(0)  # Reset file pointer
        files = {'audio': (file.name, file.read(), file.content_type)}
        data = {
        'target': language,  # Target language for translation
        'translate': should_translate  # Whether to translate or not
            }
        
        response = requests.post(
            f"{FLASK_API_URL}/transcribe",
            files=files,
            data=data,
            timeout=300  # 5 minute timeout
        )

        # Clean up temp file
        os.unlink(temp_path)

        if not response.ok:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get('error', 'Transcription service error')
            return JsonResponse({'error': error_msg}, status=response.status_code)

        result = response.json()
        
        if not result.get('success'):
            return JsonResponse({'error': result.get('error', 'Transcription failed')}, status=500)

        # Save the transcribed text (use translated text if available)
        tool = Tool.objects.get(name=TOOL_NAME)
        final_text = result.get('translated_text', result.get('original_text', ''))
        text_data = TextToolData(content=final_text)
        text_data.save()
        
        # Create usage history
        ToolUsageHistory.objects.create(
            user=request.user,
            tool=tool,
            additional_data_id=text_data.id
        )
        
        # Update user usage
        ToolUsageManager.decrement_trials(request.user, TOOL_NAME, duration)
        
        return JsonResponse({
            'success': True,
            'text': final_text,
            'text_data_id': text_data.id,
            'duration': duration,
            'was_translated': 'translated_text' in result
        })

    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Request timeout. Please try with a shorter file.'}, status=408)
    except requests.exceptions.RequestException as e:
        logger.error(f"Flask API request error: {str(e)}")
        return JsonResponse({'error': 'Transcription service unavailable'}, status=503)
    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def get_text_result(request, text_data_id):
    """Get transcribed text result"""
    try:
        text_data = get_object_or_404(TextToolData, id=text_data_id)
        
        # Verify user has access through tool usage history
        tool = Tool.objects.get(name=TOOL_NAME)
        usage_history = ToolUsageHistory.objects.filter(
            user=request.user,
            tool=tool,
            additional_data_id=text_data_id
        ).first()
        
        if not usage_history:
            return JsonResponse({'error': 'Access denied'}, status=403)
            
        return JsonResponse({
            'text': text_data.content,
            'text_data_id': text_data_id
        })
        
    except TextToolData.DoesNotExist:
        return JsonResponse({'error': 'Text not found'}, status=404)

@login_required
def get_trials_left_api(request):
    """Endpoint to get remaining trial time for current user"""
    try:
        trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        
        return JsonResponse({
            'trials_left': trials_left,
            'max_input': 1800  # Maximum allowed audio duration (5 minutes)
        })
        
    except Tool.DoesNotExist:
        logger.error(f"Tool {TOOL_NAME} not found")
        return JsonResponse({
            'error': 'Tool not found',
            'trials_left': 0,
            'max_input': 1800
        }, status=500)

def is_valid_audio(file):
    """Validate audio file"""
    allowed_types = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/m4a', 'video/mp4', 'video/webm', 'video/quicktime']
    max_size = 500 * 1024 * 1024  # 500MB OpenAI limit

    return (file.content_type in allowed_types and
            file.size <= max_size and
            file.name.lower().endswith(('.mp3', '.wav', '.m4a', '.mp4', '.webm', '.mov')))