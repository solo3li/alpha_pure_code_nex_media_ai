from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.urls import reverse
from core_apps.tool_data.models import MapToolData
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.subscriptions.usage_manager import ToolUsageManager
from .utils.tool_utils import get_tool_id
import requests
import json
import uuid
from urllib.parse import unquote
FLASK_API_URL = "http://make_my_trip:5010"
FLASK_API_KEY = "your-secure-api-key-here"

@login_required
def results(request):
    token_str = request.GET.get("token")
    map = get_object_or_404(MapToolData, token=token_str)
    return render(request, 'make_my_trip/index.html')

@login_required
def home(request):
    user_id = request.user.id
    tool_name = "make-my-trip"  # Example tool name

    try:
        has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
        if not has_phone_number:    
            return redirect('home:home')
        tool = Tool.objects.filter(name=tool_name).first()
        if not tool:
            return render(request, 'make_my_trip/index.html', {'number_of_trials': "Tool not found"})

        tool_id = tool.id

        tool_id = tool.id

        number_of_trials = ToolUsageManager.get_trials_left(request.user, tool_name)

    except Exception as err:
        print(f"Database Error: {err}")
        number_of_trials = "Error fetching trials"

    return render(request, 'make_my_trip/itinerary_form.html', {'number_of_trials': number_of_trials})

@login_required
def get_user_info(request):
    tool_name = "make-my-trip"
    user_id = request.user.id

    # Check trial or subscription


    place = request.GET.get('place')
    if not place:
        return JsonResponse({
            'status': 'error',
            'message': 'Location is required. Please choose a location.'
        }, status=400)  # Bad Request

    # Decode the place name (e.g., "Cairo%2C%20Egypt" -> "Cairo, Egypt")
    place = unquote(place)

    url_params = request.GET.dict()
    url_params.pop('place', None)

    # Make API call to the Flask backend with X-API-Key
    flask_api_url = FLASK_API_URL + "/process_map_data"
    
    headers = {
        'X-API-Key': FLASK_API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Prepare data for the Flask API
    api_data = {
        'place': place,
        'url_params': url_params,
        'user_id': str(user_id),
    }
    
    try:
        # Call Flask API
        response = requests.post(flask_api_url, json=api_data, headers=headers)
        response_data = response.json()
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error', 
                'message': response_data.get('message', 'Error processing request')
            }, status=response.status_code)
        
        # If successful, process the response from Flask API
        data = response_data.get('data')
        thumbnail = response_data.get('thumbnail')
        
        # Retrieve tool ID for "make-my-trip"
        tool_id = get_tool_id(tool_name)
        if not tool_id:
            return JsonResponse({
                'status': 'error',
                'message': f"Tool '{tool_name}' not found."
            }, status=404)  # Not Found


        
        # Save map data (using the method from the Flask API response)
        token = uuid.uuid4()
        map_data = MapToolData(
            place=place,
            data=json.dumps(data),
            thumbnail=thumbnail,
            token=token
        )
        map_data.save()
        
        # Create usage history record
        tool_usage_history = ToolUsageHistory(
            user_id=user_id,
            tool_id=tool_id,
            processed_date=response_data.get('processed_date'),
            additional_data_id=map_data.id
        )
        tool_usage_history.save()

        # Generate a token for the frontend
        
        str_token = str(token)

        ToolUsageManager.decrement_trials(request.user, tool_name, 1)
        return JsonResponse({
            'status': 'success',
            'token': str_token
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'status': 'error',
            'message': f"Failed to connect to processing API: {str(e)}"
        }, status=500)  # Internal Server Error
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f"An unexpected error occurred: {str(e)}"
        }, status=500)  # Internal Server Error


@login_required
def get_trials_left_endpoint(request):
    return JsonResponse({"trials_left": ToolUsageManager.get_trials_left(request.user, "make-my-trip")})


@login_required
def get_my_data(request):
    user_id = request.user.id
    token_str = request.GET.get("token")

    if not token_str:
        return JsonResponse({"error": "Missing token parameter"}, status=400)
    
    try:
        # Fetch the latest map tool data for the user
        token = uuid.UUID(token_str) 
        map_data = get_object_or_404(MapToolData, token=token)
        return JsonResponse(json.loads(map_data.data), status=200)

    except ValueError:
        return JsonResponse({"error": "Invalid token format"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

@login_required
def subscribe(request):
    # Subscription view implementation
    return render(request, 'make_my_trip/subscribe.html')