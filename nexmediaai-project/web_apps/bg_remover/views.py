import json
import os
from django.shortcuts import get_object_or_404, redirect, render
import requests
from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import FileToolData
from core_apps.subscriptions.models import Subscription
from core_apps.subscriptions.usage_manager import ToolUsageManager
from datetime import date

TEMP_UPLOAD_DIR = os.path.join(settings.MEDIA_ROOT, 'tmp', 'bg_remover')
FLASK_SERVICE_URL = os.getenv('FLASK_BG_REMOVER_URL', 'http://bg_remover:5000')
TOOL_NAME = "bg-remover"
OUTPUT_PATH = os.path.join(settings.MEDIA_ROOT, 'history', 'bg_remover')
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

@login_required
def home(request):
    tool_name = "bg-remover"
    tool = Tool.objects.get(name=tool_name)
    usage = ToolUsage.objects.filter(user=request.user, tool=tool).first()

    has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
    if not has_phone_number:    
        return redirect('home:home')
        
    number_of_trials = ToolUsageManager.get_trials_left(request.user, tool_name)
    
    context = {
        'number_of_trials': number_of_trials,
        'tool_name': tool_name,
        'static_url': '/static/bg_remover/'  # Update this based on your static files setup
    }
    return render(request, 'bg_remover/index.html', context)

@login_required
def get_trials_left(request):
    """Preserved endpoint for frontend"""
    trials_left = ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
    return JsonResponse({'trials_left': trials_left})

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def upload_file(request):
    if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 1):
        return JsonResponse({
            'show': 'No-sub-no-Trial',
            'subscribe_url': '/subscriptions/upgrade/',
            'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        }, status=403)

    file = request.FILES.get('file')
    if not file or not is_valid_image(file):
        return JsonResponse({'error': 'Invalid file'}, status=400)

    filename = file.name
    saved_path = os.path.join(TEMP_UPLOAD_DIR, filename)

    with open(saved_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    try:
        print(FLASK_SERVICE_URL)
        with open(saved_path, 'rb') as file_obj:
            response = requests.post(
                f"{FLASK_SERVICE_URL}/upload",
                files={'image': (filename, file_obj)},
                headers={
                    'X-User-ID': str(request.user.id),
                    'X-Api-Key': "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"
                },
                timeout=1000
            )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Flask upload error: {str(e)}'}, status=500)

    return JsonResponse({
        'filename': filename,
        'show': 'No-sub-free-Trial',
        'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def remove_bg(request):
    try:
        data = json.loads(request.body)
        filename = data.get('filename')
        if not filename:
            return JsonResponse({'error': 'No filename provided'}, status=400)

        if not ToolUsageManager.has_valid_subscription_or_trial(request.user, TOOL_NAME, 1):
            return JsonResponse({
                'show': 'No-sub-no-Trial',
                'subscribe_url': '/subscriptions/upgrade/',
                'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
            }, status=403)

        response = requests.post(
            f"{FLASK_SERVICE_URL}/process",
            json={'filename': filename},
            headers={
                'X-User-ID': str(request.user.id),
                'X-Api-Key': settings.FLASK_SERVICE_API_KEY
            },
            timeout=700
        )
        response.raise_for_status()
        result = response.json()

        # Create file data entry and link it to the user
        file_data = FileToolData.objects.create(
            user=request.user,  # Link the file to the logged-in user
            file_name=result['output_filename'],
            file_path=os.path.join(OUTPUT_PATH, result['output_filename']),
        )

        tool = Tool.objects.get(name=TOOL_NAME)
        ToolUsageHistory.objects.create(
            user=request.user,
            tool=tool,
            additional_data_id=file_data.id
        )
        ToolUsageManager.decrement_trials(request.user, TOOL_NAME, 1)

        return JsonResponse({
            'result': result,
            'show': f'/bg-remover/output/image/{file_data.id}/',
            'trials': ToolUsageManager.get_trials_left(request.user, TOOL_NAME)
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



@login_required
def serve_output_image(request, file_id):
    """Preserved image serving endpoint that restricts access to the image owner only."""
    # Ensure the file exists and belongs to the logged-in user
    file_data = get_object_or_404(FileToolData, id=file_id, user=request.user)

    # If file found and belongs to the user, return the image
    try:
        return FileResponse(open(file_data.file_path, 'rb'), content_type='image/png')
    except FileNotFoundError:
        return JsonResponse({'error': 'File not found'}, status=404)

    # If the file does not belong to the user, return an error
    return JsonResponse({'error': 'You do not have permission to access this file'}, status=403)

@login_required
def download_processed(request):
    """Preserved download endpoint"""
    file_id = request.session.get('processed_file_id')
    if not file_id:
        return JsonResponse({'error': 'No file to download'}, status=400)

    # Ensure the file belongs to the logged-in user
    file_data = get_object_or_404(FileToolData, id=file_id, user=request.user)

    return FileResponse(open(file_data.file_path, 'rb'), as_attachment=True)

# Helper functions
def is_valid_image(file):
    """Validate image file"""
    allowed_types = ['image/png', 'image/jpeg', 'image/webp']
    return (file.content_type in allowed_types and 
            file.size <= 10 * 1024 * 1024)  # 10MB max