from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from loguru import logger
import requests
import json
import os
import uuid
import traceback
from core_apps.tools.models import User, Tool, ToolUsage
from core_apps.subscriptions.models import Subscription, Plan
from core_apps.subscriptions.usage_manager import ToolUsageManager
from django.http import HttpResponseForbidden

from .models import (
    DarijatVoice,
    DarijatDialect,
    DarijatEmotion,
    DarijatStyle,
    GeminiTTSConfig,
    TTSProcessing,
)
from .tasks import (
    generate_openai_audio_task,
    generate_darijat_audio_task,
    generate_gemini_audio_task,
)

# API configuration
FLASK_API_URL = "http://text_to_voice:5008"
API_KEY = "G7OaZvkf906gDS6skW9mCnxvOLOnWnc8"

# Audio storage directory in Django
AUDIO_STORAGE_PATH = getattr(settings, 'AUDIO_STORAGE_PATH', 'audio_files/')

# ─── Tier configuration ──────────────────────────────────────────────────────
FREE_ARABIC_CHAR_LIMIT = 150
SUB_ARABIC_CHAR_LIMIT = 3000


def _is_subscriber(user):
    """Return True if the user has an active subscription where start_date <= today <= end_date."""
    if not user.is_authenticated:
        return False
    try:
        from django.utils import timezone
        today = timezone.localdate()
        return Subscription.objects.filter(
            user=user,
            status='Active',
            start_date__lte=today,
            end_date__gte=today,
        ).exists()
    except Exception:
        return False


def _serialize_options(queryset, include_value=True):
    """Serialize a queryset of option models to a list of dicts for JSON."""
    items = []
    for obj in queryset:
        item = {
            'id': obj.id,
            'name': obj.name,
            'is_premium': obj.is_premium,
        }
        if include_value:
            item['value'] = obj.value
        items.append(item)
    return items


def _serialize_voices(queryset):
    """Serialize DarijatVoice queryset for JSON."""
    items = []
    for v in queryset:
        items.append({
            'id': v.id,
            'name': v.name,
            'voice_name': v.voice_name,
            'accent': v.accent,
            'gender': v.gender,
            'is_premium': v.is_premium,
            'has_demo': v.has_demo,
            'demo_url': v.demo_audio.url if v.demo_audio else None,
        })
    return items


def home(request):
    try:
        tool_name = "text-to-voice"
        is_subscriber = _is_subscriber(request.user)

        # Load DB-driven options for Arabic TTS
        voices = DarijatVoice.objects.filter(is_active=True)
        dialects = DarijatDialect.objects.filter(is_active=True)
        emotions = DarijatEmotion.objects.filter(is_active=True)
        styles = DarijatStyle.objects.filter(is_active=True)

        # Serialize for template JS
        voices_json = json.dumps(_serialize_voices(voices), ensure_ascii=False)
        dialects_json = json.dumps(_serialize_options(dialects), ensure_ascii=False)
        emotions_json = json.dumps(_serialize_options(emotions), ensure_ascii=False)
        styles_json = json.dumps(_serialize_options(styles), ensure_ascii=False)
        use_gemini = GeminiTTSConfig.is_gemini_active()        

        active_processing = None
        active_processing_language = None

        if request.user.is_authenticated:
            has_phone_number = hasattr(request.user, 'phone_number') and request.user.phone_number is not None
            if not has_phone_number:
                return redirect('home:home')

            number_of_trials = ToolUsageManager.get_trials_left(request.user, tool_name)

            active = TTSProcessing.objects.filter(
                user=request.user,
                status__in=['PENDING', 'PROCESSING'],
            ).first()
            if active:
                active_processing = str(active.processing_id)
                active_processing_language = active.language

            return render(request, 'text_to_voice/index.html', {
                'number_of_trials': number_of_trials,
                'is_subscriber': is_subscriber,
                'free_char_limit': FREE_ARABIC_CHAR_LIMIT,
                'sub_char_limit': SUB_ARABIC_CHAR_LIMIT,
                'voices_json': voices_json,
                'dialects_json': dialects_json,
                'emotions_json': emotions_json,
                'styles_json': styles_json,
                'active_processing_id': active_processing,
                'active_processing_language': active_processing_language,
                'use_gemini': use_gemini,
            })
        else:
            return render(request, 'text_to_voice/index.html', {
                'number_of_trials': "Login First",
                'is_subscriber': False,
                'free_char_limit': FREE_ARABIC_CHAR_LIMIT,
                'sub_char_limit': SUB_ARABIC_CHAR_LIMIT,
                'voices_json': voices_json,
                'dialects_json': dialects_json,
                'emotions_json': emotions_json,
                'styles_json': styles_json,
                'active_processing_id': None,
                'active_processing_language': None,
                'use_gemini': use_gemini,
            })

    except Exception as err:
        print(f"Database Error: {err}")
        return render(request, 'text_to_voice/index.html', {
            'number_of_trials': "Login First",
            'is_subscriber': False,
            'free_char_limit': FREE_ARABIC_CHAR_LIMIT,
            'sub_char_limit': SUB_ARABIC_CHAR_LIMIT,
            'voices_json': '[]',
            'dialects_json': '[]',
            'emotions_json': '[]',
            'styles_json': '[]',
            'active_processing_id': None,
            'active_processing_language': None,
            'use_gemini': use_gemini,
        })


def generate_audio(request):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Login first to use this tool.")
        try:
            data = json.loads(request.body)
            text = data.get('text', '')
            language = data.get('language', 'other')   # 'other' or 'arabic'
            is_subscriber = _is_subscriber(request.user)
            tool_name = "text-to-voice"

            # ── Basic validation ──────────────────────────────────────────────
            if not text or not text.strip():
                return JsonResponse({"error": "Text is required"}, status=400)

            # ── Auto-expire stale records before the guard ────────────────────
            # Any record stuck in PENDING/PROCESSING for more than 10 minutes
            # is considered dead (crashed worker, network failure, etc.).
            # Mark it FAILED so the user is not permanently locked out.
            stale_cutoff = timezone.now() - timezone.timedelta(minutes=10)
            stale_qs = TTSProcessing.objects.filter(
                user=request.user,
                status__in=['PENDING', 'PROCESSING'],
                updated_at__lt=stale_cutoff,
            )
            stale_count = stale_qs.count()
            if stale_count:
                stale_qs.update(
                    status='FAILED',
                    error_message='انتهت مهلة المعالجة تلقائياً (timeout)',
                )
                logger.warning(
                    f"[generate_audio] Auto-expired {stale_count} stale TTS record(s) "
                    f"for user={request.user.id}"
                )

            # ── One-at-a-time guard ───────────────────────────────────────────
            active_count = TTSProcessing.objects.filter(
                user=request.user,
                status__in=['PENDING', 'PROCESSING'],
            ).count()
            if active_count >= 1:
                return JsonResponse({
                    "error": "لديك طلب قيد المعالجة. يرجى الانتظار حتى ينتهي.",
                    "show": "processing_in_progress",
                }, status=429)

            # ── Character limit enforcement ───────────────────────────────────
            if language == 'arabic':
                char_limit = SUB_ARABIC_CHAR_LIMIT if is_subscriber else FREE_ARABIC_CHAR_LIMIT
                if len(text) > char_limit:
                    return JsonResponse({
                        "error": f"Text exceeds {char_limit} character limit for your plan",
                        "show": "char_limit_exceeded",
                        "limit": char_limit,
                        "is_subscriber": is_subscriber,
                    }, status=400)
            else:
                if len(text) > 4096:
                    return JsonResponse({"error": "Text exceeds 4096 character limit"}, status=400)

            # ── Trial check ───────────────────────────────────────────────────
            trial_available = ToolUsageManager.is_trial_available(request.user, tool_name, 1)
            remaining_trials = ToolUsageManager.get_trials_left(request.user, tool_name)

            if not trial_available:
                return JsonResponse({
                    'error': 'No trials remaining',
                    'show': 'No-sub-no-Trial',
                    'trials': remaining_trials,
                })

            # char_count = len(text.replace(" ", ""))
            char_count = len(text)
            if char_count > remaining_trials:
                return JsonResponse({
                    'error': f'Text requires {char_count} characters but only {remaining_trials} remaining',
                    'show': 'No-sub-no-Trial',
                    'trials': remaining_trials,
                })

            processing_id = uuid.uuid4()

            # ── Arabic branch ─────────────────────────────────────────────────
            if language == 'arabic':
                voice_name = data.get('voice_name', '')
                style_instruction = data.get('style_instruction', '')

                if not voice_name:
                    return JsonResponse({"error": "اسم الصوت مطلوب"}, status=400)

                # Premium voice guard
                try:
                    voice_obj = DarijatVoice.objects.get(
                        voice_name=voice_name, is_active=True
                    )
                    if voice_obj.is_premium and not is_subscriber:
                        return JsonResponse({
                            "error": "prime_required",
                            "show": "prime_voice_blocked",
                            "message": "هذا الصوت متاح للمشتركين فقط.",
                        }, status=403)
                except DarijatVoice.DoesNotExist:
                    pass  # Unknown voices pass through

                # Premium option guards (dialect, emotion, style)
                if not is_subscriber:
                    selected_parts = [p.strip() for p in style_instruction.split(',') if p.strip()]
                    premium_dialect_values = set(
                        DarijatDialect.objects.filter(is_premium=True, is_active=True)
                        .values_list('value', flat=True)
                    )
                    premium_emotion_values = set(
                        DarijatEmotion.objects.filter(is_premium=True, is_active=True)
                        .values_list('value', flat=True)
                    )
                    premium_style_values = set(
                        DarijatStyle.objects.filter(is_premium=True, is_active=True)
                        .values_list('value', flat=True)
                    )
                    all_premium = premium_dialect_values | premium_emotion_values | premium_style_values
                    for part in selected_parts:
                        if part in all_premium:
                            return JsonResponse({
                                "error": "premium_option_required",
                                "show": "prime_voice_blocked",
                                "message": "هذا الخيار متاح للمشتركين فقط.",
                            }, status=403)

                    known_values = set(
                        DarijatDialect.objects.filter(is_active=True).values_list('value', flat=True)
                    ) | set(
                        DarijatEmotion.objects.filter(is_active=True).values_list('value', flat=True)
                    ) | set(
                        DarijatStyle.objects.filter(is_active=True).values_list('value', flat=True)
                    )
                    custom_parts = [p for p in selected_parts if p not in known_values]
                    if custom_parts:
                        return JsonResponse({
                            "error": "premium_custom_prompt",
                            "show": "prime_voice_blocked",
                            "message": "الإرشادات المخصصة متاحة للمشتركين فقط.",
                        }, status=403)

                # ── Create DB record ──────────────────────────────────────────
                record = TTSProcessing.objects.create(
                    user=request.user,
                    processing_id=processing_id,
                    language='arabic',
                    text=text,
                    voice_name=voice_name,
                    style_instruction=style_instruction,
                    char_count=char_count,
                    status='PENDING',
                )

                # ── Route to Gemini or Darijat based on config ────────────────
                use_gemini = GeminiTTSConfig.is_gemini_active()

                if use_gemini:
                    logger._info = lambda msg: None  # silence any stray import issues
                    import logging
                    logging.getLogger(__name__).info(
                        f"[generate_audio] Routing arabic request to Gemini TTS "
                        f"(processing_id={processing_id})"
                    )
                    task = generate_gemini_audio_task.delay(str(processing_id))
                else:
                    task = generate_darijat_audio_task.delay(str(processing_id))

                record.celery_task_id = task.id
                record.save(update_fields=['celery_task_id'])

            # ── Non-Arabic branch (OpenAI) ────────────────────────────────────
            else:
                voice = data.get('voice', 'alloy')
                speed = data.get('speed', 1.0)
                fmt = data.get('format', 'mp3')

                valid_voices = [
                    'alloy', 'ash', 'ballad', 'coral', 'echo', 'fable',
                    'nova', 'onyx', 'sage', 'shimmer', 'verse',
                ]
                if voice not in valid_voices:
                    return JsonResponse({
                        "error": f"Invalid voice. Must be one of: {', '.join(valid_voices)}"
                    }, status=400)

                record = TTSProcessing.objects.create(
                    user=request.user,
                    processing_id=processing_id,
                    language='other',
                    text=text,
                    voice_name=voice,
                    openai_voice=voice,
                    openai_speed=speed,
                    openai_format=fmt,
                    char_count=char_count,
                    status='PENDING',
                )

                task = generate_openai_audio_task.delay(str(processing_id))
                record.celery_task_id = task.id
                record.save(update_fields=['celery_task_id'])

            return JsonResponse({
                'processing_id': str(processing_id),
                'status': 'PENDING',
                'message': 'تم إرسال الطلب. جاري المعالجة...',
            })

        except json.JSONDecodeError as json_error:
            print(f"JSON decode error: {json_error}")
            return JsonResponse({"error": "Invalid request format"}, status=400)
        except Exception as e:
            print(f"Unexpected error in generate_audio: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"})

    return JsonResponse({"error": "Method not allowed"}, status=405)


@login_required
def check_tts_status(request, processing_id):
    """Polling endpoint: check the status of a TTS processing task."""
    try:
        record = TTSProcessing.objects.get(
            processing_id=processing_id,
            user=request.user,
        )

        response_data = {
            'status': record.status,
            'processing_id': str(record.processing_id),
        }

        if record.status == 'COMPLETED' and record.result_file:
            filename = os.path.basename(record.result_file)
            response_data['audio_url'] = f'/text-to-voice/download_audio/{filename}'

        if record.status == 'FAILED':
            response_data['error_message'] = record.error_message or 'حدث خطأ غير متوقع'

        return JsonResponse(response_data)

    except TTSProcessing.DoesNotExist:
        return JsonResponse({
            'status': 'FAILED',
            'error_message': 'المهمة غير موجودة أو انتهت صلاحيتها.',
        })


@login_required
def download_audio(request, filename):
    """Serve audio files stored locally in Django."""
    try:
        file_path = os.path.join(AUDIO_STORAGE_PATH, filename)

        print(f"Attempting to serve file: {file_path}")

        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return JsonResponse({"error": "File not found"}, status=404)

        # Security: file must belong to the requesting user
        expected_prefix = f"{request.user.id}_"
        if not filename.startswith(expected_prefix):
            print(f"Unauthorized access attempt: {filename} doesn't start with {expected_prefix}")
            return JsonResponse({"error": "Unauthorized access"}, status=403)

        file_size = os.path.getsize(file_path)
        print(f"Serving audio file: {filename}, size: {file_size} bytes")

        file_extension = filename.split('.')[-1].lower()
        content_type_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'opus': 'audio/opus',
            'aac': 'audio/aac',
            'flac': 'audio/flac',
            'pcm': 'audio/pcm',
        }
        content_type = content_type_map.get(file_extension, 'application/octet-stream')

        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = str(file_size)
            return response

    except Exception as e:
        print(f"Error serving audio file: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def serve_voice_demo(request, voice_id):
    """Serve voice demo audio file from the database model."""
    try:
        voice = DarijatVoice.objects.get(id=voice_id, is_active=True)
        if not voice.demo_audio:
            return JsonResponse({"error": "No demo available"}, status=404)

        return FileResponse(
            voice.demo_audio.open('rb'),
            content_type='audio/mpeg',
            as_attachment=False,
        )
    except DarijatVoice.DoesNotExist:
        return JsonResponse({"error": "Voice not found"}, status=404)


@login_required
def get_trials_left_endpoint(request):
    try:
        tool_name = "text-to-voice"
        trials_left = ToolUsageManager.get_trials_left(request.user, tool_name)
        return JsonResponse({'trials_left': trials_left})
    except Exception as e:
        print(f"Error getting trials left: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_history(request):
    """Return the last 20 completed/failed TTS jobs for the current user."""
    try:
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
                    audio_url = f'/text-to-voice/download_audio/{filename}'

            history.append({
                'processing_id': str(r.processing_id),
                'language': r.language,
                'voice_name': r.voice_name or '',
                'text_preview': (r.text or '')[:80],
                'char_count': r.char_count,
                'status': r.status,
                'audio_url': audio_url,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                'error_message': r.error_message if r.status == 'FAILED' else None,
            })

        return JsonResponse({'history': history})

    except Exception as e:
        print(f"Error fetching TTS history: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)