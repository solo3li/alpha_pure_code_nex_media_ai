from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
import requests
import json
from datetime import date, datetime
from core_apps.tools.models import User, Tool, ToolUsage
from core_apps.subscriptions.models import Subscription, Plan
from core_apps.subscriptions.usage_manager import ToolUsageManager


# API configuration
FLASK_API_URL = "http://gpt:5007"
API_KEY = "G7OaZvkf906gDS6skW9mCnxvOLOnWnc8"


@login_required
def home(request):
    user_id = request.user.id
    tool_name = "GPT-3.5"  
    
    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        tool = Tool.objects.get(name=tool_name)
        tool_id = tool.id
        number_of_trials = ToolUsageManager.get_trials_left(request.user, tool_name)
        
    except Exception as err:
        print(f"Database Error: {err}")
        number_of_trials = "Error fetching trials"
    
    return render(request, 'GPT/index.html', {'number_of_trials': number_of_trials})


@login_required
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_input = data.get('message', '')
            model = data.get('model', 'gpt-4o')
            image_data = data.get('image', None)
            user_id = request.user.id
            
            # Convert model name to tool name format
            if model == "gpt-3.5-turbo":
                tool_name = "GPT-3.5"
            elif model == "gpt-4o":
                tool_name = "GPT-4o"
            
            # Check if trial is available
            trial_available = ToolUsageManager.is_trial_available(request.user, tool_name, 1)
            remaining_trials = ToolUsageManager.get_trials_left(request.user, tool_name)
            
            word_count = len(user_input.split())
            if word_count > remaining_trials:
                return JsonResponse({
                    "response": f"Sorry, you are out of credits. Your remaining words: {remaining_trials}. Press on <a href='https://www.nexmediaai.com/subscribe' target='_blank'>Subscribe</a> To add more credits"
                })
            
            # Make API call to Flask service
            api_response = requests.post(
                f"{FLASK_API_URL}/api/chat",
                json={
                    'message': user_input,
                    'model': model,
                    'image': image_data
                },
                headers={
                    'X-API-Key': API_KEY
                }
            )
            
            if api_response.status_code == 200:
                response_data = api_response.json()
                # Update usage after successful API call
                ToolUsageManager.decrement_trials(request.user, model, word_count)
                return JsonResponse(response_data)
            else:
                return JsonResponse({"error": "API Error: " + api_response.text})
                
        except Exception as e:
            return JsonResponse({"error": str(e)})
    
    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def get_trials_left_endpoint(request):
    try:
        user_id = request.user.id
        tool_name = request.GET.get('tool_name')
        
        if not tool_name:
            return JsonResponse({'error': 'Tool name is required'}, status=400)
        
        # Validate tool_name
        valid_tools = ['gpt-3.5-turbo', 'gpt-4o']
        if tool_name not in valid_tools:
            return JsonResponse({'error': 'Invalid tool name. Must be GPT-3.5 or GPT-4'}, status=400)
            
        if tool_name == "gpt-3.5-turbo":
            tool_name = "GPT-3.5"
        elif tool_name == "gpt-4o":
            tool_name = "GPT-4o"
            
        trials_left = ToolUsageManager.get_trials_left(request.user, tool_name)
        return JsonResponse({'trials_left': trials_left})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


