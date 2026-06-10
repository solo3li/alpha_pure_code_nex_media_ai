# text_to_voice/tasks.py
from core_apps.subscriptions import context_processors
import os
import struct
import traceback
import requests
from celery import shared_task
from django.conf import settings
from loguru import logger
from django.utils import timezone

from core_apps.subscriptions.usage_manager import ToolUsageManager

TOOL_NAME = "text-to-voice"
FLASK_API_URL = "http://text_to_voice:5008"
API_KEY = "G7OaZvkf906gDS6skW9mCnxvOLOnWnc8"

# Darijat API — called directly from Celery (no Flask middleman)
DARIJAT_API_URL = "https://tts.darijat.com/api/v1/external/generate-audio"
DARIJAT_API_KEY = "1|UhPDOocWKIW8Q767wWD17Z0cK15cmHNQ"

# Gemini TTS — called directly from Celery
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_API_KEY = "AIzaSyCDsTkUcNWBHOqOdcpinFEhJVAYxlj_cwQ"

AUDIO_STORAGE_PATH = getattr(settings, 'AUDIO_STORAGE_PATH', 'audio_files/')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_error(response):
    """Try to extract an error message from an HTTP response."""
    try:
        data = response.json()
        return data.get('error') or data.get('message') or str(data)
    except Exception:
        return response.text[:200] if response.text else f"HTTP {response.status_code}"


def _build_gemini_prompt(text: str, style_instruction: str) -> str:
    """
    Build the Gemini TTS prompt from the user's text and style_instruction.
    The preamble must be in English to pass Gemini's speech synthesis classifier.
    """
    # Always start with an English TTS instruction — this is required to
    # activate the speech synthesis classifier and avoid PROHIBITED_CONTENT blocks.
    if not style_instruction or not style_instruction.strip():
        return f"Read the following text aloud:\n\n{text.strip()}"

    # Map Arabic style tags to English direction for the classifier
    parts = [p.strip() for p in style_instruction.split(',') if p.strip()]

    # Build an English direction line + keep Arabic tags inline if needed
    direction = ', '.join(parts)
    return f"Read the following text aloud in this style: {direction}\n\n{text.strip()}"


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000,
                num_channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Wrap raw PCM bytes in a WAV header."""
    data_size = len(pcm_data)
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    block_align = num_channels * (bits_per_sample // 8)
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,               # Subchunk1Size (PCM)
        1,                # AudioFormat (PCM = 1)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + pcm_data


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI TTS task (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, time_limit=600, soft_time_limit=540)
def generate_openai_audio_task(self, processing_id):
    """Celery task: generate audio via OpenAI TTS (through Flask service)."""

    from .models import TTSProcessing

    processing_id_str = str(processing_id)

    try:
        record = TTSProcessing.objects.get(processing_id=processing_id_str)
    except TTSProcessing.DoesNotExist:
        logger.error(f"TTSProcessing not found: {processing_id_str}")
        return

    try:
        record.status = 'PROCESSING'
        record.save(update_fields=['status', 'updated_at'])

        logger.info(f"[OpenAI TTS] Starting for {processing_id_str}, user={record.user_id}")

        payload = {
            'text': record.text,
            'voice': record.openai_voice or 'alloy',
            'model': 'tts-1',
            'speed': record.openai_speed,
            'format': record.openai_format or 'mp3',
            'user_id': str(record.user_id),
        }

        api_response = requests.post(
            f"{FLASK_API_URL}/api/generate_openai_audio",
            json=payload,
            headers={
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json',
            },
            stream=True,
            timeout=300,
        )

        if api_response.status_code != 200:
            error_msg = _extract_error(api_response)
            raise Exception(f"Flask API error ({api_response.status_code}): {error_msg}")

        content_type = api_response.headers.get('content-type', '')
        if 'audio' not in content_type and 'octet-stream' not in content_type:
            raise Exception(f"Unexpected content-type: {content_type}")

        fmt = record.openai_format or 'mp3'
        filename = f"{record.user_id}_{processing_id_str}.{fmt}"
        file_path = os.path.join(AUDIO_STORAGE_PATH, filename)
        os.makedirs(os.path.dirname(file_path) or AUDIO_STORAGE_PATH, exist_ok=True)

        with open(file_path, 'wb') as f:
            for chunk in api_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        if file_size == 0:
            raise Exception("Generated audio file is empty")

        logger.info(f"[OpenAI TTS] Audio saved: {file_path} ({file_size} bytes)")

        ToolUsageManager.decrement_trials(record.user, TOOL_NAME, record.char_count)

        record.status = 'COMPLETED'
        record.result_file = file_path
        record.save(update_fields=['status', 'result_file', 'updated_at'])

        logger.info(f"[OpenAI TTS] Completed for {processing_id_str}")

    except Exception as exc:
        logger.error(f"[OpenAI TTS] Failed for {processing_id_str}: {exc}")
        logger.error(traceback.format_exc())

        record.status = 'FAILED'
        record.error_message = str(exc)[:497]
        record.save(update_fields=['status', 'error_message', 'updated_at'])

        retry_count = self.request.retries
        countdown = min(30 * (retry_count + 1), 120)
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"[OpenAI TTS] Max retries exceeded for {processing_id_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Darijat TTS task (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, time_limit=600, soft_time_limit=540)
def generate_darijat_audio_task(self, processing_id):
    """Celery task: generate Arabic audio via Darijat TTS API (direct call)."""

    from .models import TTSProcessing

    processing_id_str = str(processing_id)

    try:
        record = TTSProcessing.objects.get(processing_id=processing_id_str)
    except TTSProcessing.DoesNotExist:
        logger.error(f"TTSProcessing not found: {processing_id_str}")
        return

    try:
        record.status = 'PROCESSING'
        record.save(update_fields=['status', 'updated_at'])

        logger.info(
            f"[Darijat TTS] Starting for {processing_id_str}, "
            f"user={record.user_id}, voice={record.voice_name}"
        )

        payload = {
            'text': record.text,
            'voice_name': record.voice_name,
            'human_simulation': True,
        }

        if record.style_instruction.strip():
            payload['style_instruction'] = record.style_instruction.strip()

        logger.info(f"[Darijat TTS] Payload: {payload}")

        session = requests.Session()
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        resp = session.post(
            DARIJAT_API_URL,
            json=payload,
            headers={
                'Authorization': f'Bearer {DARIJAT_API_KEY}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            timeout=(30, 240),
            stream=True,
        )

        logger.info(f"[Darijat TTS] Response status: {resp.status_code}")

        if resp.status_code != 200:
            error_msg = _extract_error(resp)
            raise Exception(f"Darijat API error ({resp.status_code}): {error_msg}")

        filename = f"{record.user_id}_{processing_id_str}_arabic.mp3"
        file_path = os.path.join(AUDIO_STORAGE_PATH, filename)
        os.makedirs(os.path.dirname(file_path) or AUDIO_STORAGE_PATH, exist_ok=True)

        content_type = resp.headers.get('content-type', '')

        if 'application/json' in content_type:
            resp_data = resp.json()
            audio_url = (
                resp_data.get('audio_url')
                or resp_data.get('url')
                or resp_data.get('data', {}).get('audio_url')
            )

            if audio_url:
                logger.info(f"[Darijat TTS] Got audio URL: {audio_url}")
                audio_resp = session.get(audio_url, stream=True, timeout=(30, 240))
                audio_resp.raise_for_status()

                with open(file_path, 'wb') as f:
                    for chunk in audio_resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            else:
                raise Exception(f"Darijat API returned JSON without audio URL: {resp_data}")
        else:
            with open(file_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        if file_size == 0:
            raise Exception("Generated audio file is empty")

        logger.info(f"[Darijat TTS] Audio saved: {file_path} ({file_size} bytes)")

        ToolUsageManager.decrement_trials(record.user, TOOL_NAME, record.char_count)

        record.status = 'COMPLETED'
        record.result_file = file_path
        record.save(update_fields=['status', 'result_file', 'updated_at'])

        logger.info(f"[Darijat TTS] Completed for {processing_id_str}")

    except Exception as exc:
        logger.error(f"[Darijat TTS] Failed for {processing_id_str}: {exc}")
        logger.error(traceback.format_exc())

        record.status = 'FAILED'
        record.error_message = str(exc)[:497]
        record.save(update_fields=['status', 'error_message', 'updated_at'])

        retry_count = self.request.retries
        countdown = min(60 * (retry_count + 1), 180)
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"[Darijat TTS] Max retries exceeded for {processing_id_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Gemini TTS task  ← NEW
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, time_limit=600, soft_time_limit=540)
def generate_gemini_audio_task(self, processing_id):
    """
    Celery task: generate Arabic audio via Gemini TTS API.

    This is used as a drop-in replacement for generate_darijat_audio_task
    when GeminiTTSConfig.use_gemini_for_arabic is True.

    Flow:
    1. Look up the DarijatVoice by voice_name → get the mapped gemini_voice.
    2. Build a styled prompt from text + style_instruction.
    3. Call Gemini generateContent with responseModality AUDIO.
    4. Decode the base64 inline_data and save as WAV.
    5. Mark record COMPLETED and decrement trials.
    """

    import base64
    from .models import TTSProcessing, DarijatVoice, GeminiTTSConfig

    processing_id_str = str(processing_id)

    try:
        record = TTSProcessing.objects.get(processing_id=processing_id_str)
    except TTSProcessing.DoesNotExist:
        logger.error(f"[Gemini TTS] TTSProcessing not found: {processing_id_str}")
        return

    try:
        record.status = 'PROCESSING'
        record.save(update_fields=['status', 'updated_at'])

        # ── Resolve Gemini voice name ─────────────────────────────────────────
        gemini_voice = None
        try:
            voice_obj = DarijatVoice.objects.get(
                voice_name=record.voice_name, is_active=True
            )
            gemini_voice = voice_obj.get_gemini_voice()
        except DarijatVoice.DoesNotExist:
            pass

        if not gemini_voice:
            cfg = GeminiTTSConfig.get_config()
            gemini_voice = cfg.fallback_gemini_voice if cfg else 'Zephyr'

        # ── Resolve model ─────────────────────────────────────────────────────
        cfg = GeminiTTSConfig.get_config()
        gemini_model = cfg.gemini_model if cfg else 'gemini-3.1-flash-tts-preview'

        logger.info(
            f"[Gemini TTS] Starting for {processing_id_str}, "
            f"user={record.user_id}, darijat_voice={record.voice_name}, "
            f"gemini_voice={gemini_voice}, model={gemini_model}"
        )

        # ── Build prompt ──────────────────────────────────────────────────────
        prompt = _build_gemini_prompt(record.text, record.style_instruction)
        logger.info(f"[Gemini TTS] Prompt (first 200 chars): {prompt[:200]}")

        # ── Call Gemini REST API ──────────────────────────────────────────────
        api_key = GEMINI_API_KEY
        if not api_key:
            raise Exception("GEMINI_API_KEY environment variable is not set")

        url = GEMINI_API_URL.format(model=gemini_model)
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": gemini_voice
                        }
                    }
                }
            }
        }

        resp = requests.post(
            url,
            json=payload,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            timeout=(30, 300),
        )

        logger.info(f"[Gemini TTS] Response status: {resp.status_code}")

        if resp.status_code != 200:
            error_msg = _extract_error(resp)
            raise Exception(f"Gemini API error ({resp.status_code}): {error_msg}")

        resp_data = resp.json()
        print(f"[Gemini TTS] Full response: {str(resp_data)[:2000]}")

        # ── Extract audio from response ───────────────────────────────────────
        # Gemini returns: candidates[0].content.parts[0].inlineData.data (base64)
        try:
            candidates = resp_data.get('candidates', [])
            if candidates:
                finish_reason = candidates[0].get('finishReason', '')
                if finish_reason == 'PROHIBITED_CONTENT':
                    raise Exception(f"Gemini rejected prompt as PROHIBITED_CONTENT. "
                                    f"Add a clear TTS preamble to your prompt.")
            if not candidates:
                raise Exception("Gemini response has no candidates")

            parts = candidates[0].get('content', {}).get('parts', [])
            if not parts:
                raise Exception("Gemini response candidate has no parts")

            inline_data = parts[0].get('inlineData') or parts[0].get('inline_data')
            if not inline_data:
                raise Exception(
                    f"Gemini response part has no inlineData. Part keys: {list(parts[0].keys())}"
                )

            audio_b64 = inline_data.get('data', '')
            mime_type = inline_data.get('mimeType', inline_data.get('mime_type', 'audio/L16;rate=24000'))

            if not audio_b64:
                raise Exception("Gemini inlineData.data is empty")

        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini response structure: {e}. Response: {str(resp_data)[:500]}")

        # ── Decode and convert to WAV ─────────────────────────────────────────
        raw_audio = base64.b64decode(audio_b64)

        # Parse sample rate from mime_type (e.g. "audio/L16;rate=24000")
        sample_rate = 24000
        bits_per_sample = 16
        for part in mime_type.split(';'):
            part = part.strip()
            if part.lower().startswith('rate='):
                try:
                    sample_rate = int(part.split('=', 1)[1].strip())
                except (ValueError, IndexError):
                    pass
            if part.lower().startswith('audio/l'):
                try:
                    bits_per_sample = int(part.lower().split('audio/l', 1)[1].strip())
                except (ValueError, IndexError):
                    pass

        # Also fix the PCM check:
        if mime_type.lower().startswith('audio/l') or 'pcm' in mime_type.lower():
            audio_data = _pcm_to_wav(raw_audio, sample_rate=sample_rate, bits_per_sample=bits_per_sample)
            ext = 'wav'
        else:
            audio_data = raw_audio
            ext = 'mp3'

        # ── Save to disk ──────────────────────────────────────────────────────
        filename = f"{record.user_id}_{processing_id_str}.{ext}"
        file_path = os.path.join(AUDIO_STORAGE_PATH, filename)
        os.makedirs(os.path.dirname(file_path) or AUDIO_STORAGE_PATH, exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(audio_data)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        if file_size == 0:
            raise Exception("Generated Gemini audio file is empty")

        logger.info(f"[Gemini TTS] Audio saved: {file_path} ({file_size} bytes)")

        # ── Decrement trials & mark complete ──────────────────────────────────
        ToolUsageManager.decrement_trials(record.user, TOOL_NAME, record.char_count)

        record.status = 'COMPLETED'
        record.result_file = file_path
        record.save(update_fields=['status', 'result_file', 'updated_at'])

        logger.info(f"[Gemini TTS] Completed for {processing_id_str}")

    except Exception as exc:
        logger.error(f"[Gemini TTS] Failed for {processing_id_str}: {exc}")
        logger.error(traceback.format_exc())

        try:
            record.status = 'FAILED'
            record.error_message = str(exc)[:497]
            record.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception:
            pass

        retry_count = self.request.retries
        countdown = min(60 * (retry_count + 1), 180)
        try:
            raise self.retry(exc=exc, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"[Gemini TTS] Max retries exceeded for {processing_id_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Cleanup task (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name='text_to_voice.tasks.cleanup_old_tts_files')
def cleanup_old_tts_files():
    from .models import TTSProcessing

    cutoff = timezone.now() - timezone.timedelta(days=7)
    old_records = TTSProcessing.objects.filter(created_at__lt=cutoff)

    deleted_files = 0
    missing_files = 0
    deleted_records = 0
    errors = 0

    for record in old_records:
        if record.result_file:
            filename = os.path.basename(record.result_file)
            file_path = os.path.join(AUDIO_STORAGE_PATH, filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_files += 1
                    logger.debug(f'Deleted audio file: {file_path}')
                else:
                    missing_files += 1
            except OSError as e:
                logger.warning(f'Could not delete audio file {file_path}: {e}')
                errors += 1

        try:
            record.delete()
            deleted_records += 1
        except Exception as e:
            logger.error(f'Could not delete TTSProcessing record {record.processing_id}: {e}')
            errors += 1

    summary = (
        f'TTS cleanup complete — '
        f'records deleted: {deleted_records}, '
        f'audio files deleted: {deleted_files}, '
        f'missing files skipped: {missing_files}, '
        f'errors: {errors}'
    )
    logger.info(summary)
    return summary