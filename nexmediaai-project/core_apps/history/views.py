# history/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
import os
import json

from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import FileToolData, TextToolData, MapToolData


@login_required
def history_by_tool(request, tool_name):
    """Display history based on tool name"""
    
    # Define tool categories
    image_tools = ['bg-remover', 'text-to-cartoon']
    text_tools = ['img-to-txt', 'voice-to-text', 'voice to text']
    custom_tools = ['make-my-trip']
    tts_tools    = ['text-to-voice'] 
    
    if tool_name in image_tools:
        return render(request, 'history/images-history.html', {'tool_name': tool_name})
    elif tool_name in text_tools:
        return render(request, 'history/text-history.html', {'tool_name': tool_name})
    elif tool_name in custom_tools:
        return render(request, 'history/make-my-trip-history.html', {'tool_name': tool_name})
    elif tool_name in tts_tools:
        return render(request, 'history/tts-history.html', {'tool_name': tool_name})
    else:
        messages.error(request, "Invalid tool name")
        raise Http404("File not found")


@login_required
@require_http_methods(["GET"])
def get_trip_data(request, trip_id):
    """Fetch specific trip data"""
    
    try:
        # Get trip data with proper joins
        trip_history = get_object_or_404(
            ToolUsageHistory.objects.select_related('tool'),
            id=trip_id,
            user=request.user
        )
        
        # Get the associated map data
        map_data = get_object_or_404(
            MapToolData,
            id=trip_history.additional_data_id
        )
        
        trip_data = {
            "id": map_data.id,
            "place": map_data.place,
            "thumbnail": map_data.thumbnail,
            "data": map_data.data,
            "processed_date": trip_history.processed_date.isoformat()
        }
        
        return JsonResponse(trip_data)
        
    except (ToolUsageHistory.DoesNotExist, MapToolData.DoesNotExist):
        return JsonResponse({"error": "Trip not found or unauthorized access"}, status=403)


@login_required
def serve_image(request, filename):
    """Serve images securely"""
    
    try:
        # Verify ownership
        file_data = FileToolData.objects.filter(
            user=request.user,
            file_name=filename
        ).first()
        
        if not file_data:
            raise Http404("File not found")
        
        file_path = file_data.file_path
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/octet-stream')
                response['Content-Disposition'] = f'inline; filename="{filename}"'
                return response
        else:
            raise Http404("File not found")
            
    except FileToolData.DoesNotExist:
        raise Http404("File not found")


@login_required
@require_http_methods(["GET"])
def get_history(request):
    """Fetch tool usage history for image tools"""
    
    tool_name = request.GET.get('tool_name', 'text-to-cartoon')
    
    try:
        tool = Tool.objects.get(name=tool_name)
        
        # Get history with file data
        history_entries = ToolUsageHistory.objects.filter(
            user=request.user,
            tool=tool,
            additional_data_id__isnull=False
        ).order_by('-processed_date')
        
        history_data = []
        for entry in history_entries:
            try:
                file_data = FileToolData.objects.get(id=entry.additional_data_id)
                history_data.append({
                    "file_name": file_data.file_name,
                    "processed_date": entry.processed_date.isoformat(),
                    "file_path": reverse('history:serve_image', kwargs={'filename': file_data.file_name})
                })
            except FileToolData.DoesNotExist:
                continue
        
        return JsonResponse(history_data, safe=False)
        
    except Tool.DoesNotExist:
        return JsonResponse({"error": "Tool not found"}, status=404)


@login_required
@require_http_methods(["GET"])
def get_make_my_trip_history(request):
    """Fetch make-my-trip history"""
    
    try:
        # Get the make-my-trip tool
        tool = Tool.objects.get(name='make-my-trip')
        
        # Fetch history entries
        history_entries = ToolUsageHistory.objects.filter(
            user=request.user,
            tool=tool,
            additional_data_id__isnull=False
        ).order_by('-processed_date')
        
        history_data = []
        for entry in history_entries:
            try:
                map_data = MapToolData.objects.get(id=entry.additional_data_id)
                history_data.append({
                    "id": entry.id,
                    "trip_name": map_data.place,
                    "thumbnail": map_data.thumbnail,
                    "trip_date": entry.processed_date.strftime('%Y-%m-%d')
                })
            except MapToolData.DoesNotExist:
                continue
        
        return JsonResponse(history_data, safe=False)
        
    except Tool.DoesNotExist:
        return JsonResponse({"error": "Tool not found"}, status=404)


@login_required
def view_trip(request, trip_id):
    """View a specific trip"""
    
    try:
        # Get trip history
        trip_history = get_object_or_404(
            ToolUsageHistory,
            id=trip_id,
            user=request.user
        )
        
        # Get associated map data
        map_data = get_object_or_404(
            MapToolData,
            id=trip_history.additional_data_id
        )
        
        trip_data = {
            "place": map_data.place,
            "thumbnail": map_data.thumbnail,
            "data": map_data.data,
            "formatted_date": trip_history.processed_date.strftime('%Y-%m-%d')
        }
        
        return render(request, 'history/view_trip.html', {
            'trip': trip_data,
            'trip_id': trip_id
        })
        
    except (ToolUsageHistory.DoesNotExist, MapToolData.DoesNotExist):
        messages.error(request, "Trip not found")
        return redirect('history:index')


@login_required
def index(request):
    """Display the history dashboard"""

    # Get distinct tool names from standard ToolUsageHistory
    tool_names = list(
        ToolUsageHistory.objects.filter(
            user=request.user
        ).values_list('tool__name', flat=True).distinct()
    )

    try:
        from web_apps.text_to_voice.models import TTSProcessing
        has_tts = TTSProcessing.objects.filter(
            user=request.user,
            status__in=['COMPLETED', 'FAILED'],
        ).exists()
        if has_tts and 'text-to-voice' not in tool_names:
            tool_names.append('text-to-voice')
    except Exception:
        pass  # If the model isn't available, just skip it

    return render(request, 'history/history.html', {
        'tools': tool_names
    })


@login_required
@require_http_methods(["GET"])
def get_text_history(request):
    """Fetch text tool history"""
    
    tool_name = request.GET.get('tool_name', 'voice-to-text')
    
    try:
        tool = Tool.objects.get(name=tool_name)
        
        # Get history with text data
        history_entries = ToolUsageHistory.objects.filter(
            user=request.user,
            tool=tool,
            additional_data_id__isnull=False
        ).order_by('-processed_date')
        
        history_data = []
        for entry in history_entries:
            try:
                text_data = TextToolData.objects.get(id=entry.additional_data_id)
                history_data.append({
                    "content": text_data.content,
                    "processed_date": entry.processed_date.isoformat()
                })
            except TextToolData.DoesNotExist:
                continue
        
        return JsonResponse(history_data, safe=False)
        
    except Tool.DoesNotExist:
        return JsonResponse({"error": "Tool not found"}, status=404)

@login_required
@require_http_methods(["GET"])
def get_tts_history(request):
    """
    Fetch the last 20 completed/failed text-to-voice jobs for the current user.
    Mirrors the shape returned by text_to_voice.views.get_history so the
    same JS data model works in both the inline panel and this dedicated page.
    """
    from web_apps.text_to_voice.models import TTSProcessing   
    from django.conf import settings
 
    AUDIO_STORAGE_PATH = getattr(settings, 'AUDIO_STORAGE_PATH', 'audio_files/')
 
    records = TTSProcessing.objects.filter(
        user=request.user,
        status__in=['COMPLETED', 'FAILED'],
    ).order_by('-created_at')[:20]
 
    history = []
    for r in records:
        audio_url = None
        if r.status == 'COMPLETED' and r.result_file:
            filename = os.path.basename(r.result_file)
            file_path = os.path.join(AUDIO_STORAGE_PATH, filename)
            if os.path.exists(file_path):
                # Re-use the existing secure download endpoint in text_to_voice
                audio_url = f'/text-to-voice/download_audio/{filename}'
 
        history.append({
            'processing_id': str(r.processing_id),
            'language':      r.language,
            'voice_name':    r.voice_name or '',
            'text_preview':  (r.text or '')[:80],
            'char_count':    r.char_count,
            'status':        r.status,
            'audio_url':     audio_url,
            'created_at':    r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
            'error_message': r.error_message if r.status == 'FAILED' else None,
        })
 
    return JsonResponse({'history': history})