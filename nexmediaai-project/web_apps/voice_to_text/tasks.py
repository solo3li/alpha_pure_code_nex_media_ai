# voice_to_text/tasks.py
import os
import time
import requests
import hashlib
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from loguru import logger
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import TextToolData
from .models import VoiceProcessing
from celery.exceptions import TimeLimitExceeded

# Configuration
TOOL_NAME = "voice-to-text"
GPU_SERVICE_URL = "http://149.36.1.159:5006"  # Voice processing service
ORCHESTRATOR_URL = "http://orchestrator:5550"
GPU_API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

@shared_task(bind=True, max_retries=3, time_limit=1800)  # 30 minutes
def upload_audio_task(self, processing_id):
    """Upload audio file to GPU service with proper VM orchestration"""
    
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VoiceProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting audio upload task for processing_id: {processing_id}")
        
        # Update status to uploading
        record.status = 'UPLOADING'
        record.save()

        # Step 1: Ensure VM is active and ready
        logger.info(f"Ensuring VM is active for processing_id: {processing_id}")
        
        vm_activated = ensure_vm_is_active(record, processing_id,max_wait_minutes=30)
        if not vm_activated:
            raise Exception("VM failed to become active within timeout")

        # Step 2: Verify GPU service is healthy
        logger.info(f"Verifying GPU service health for processing_id: {processing_id}")
        
        if not verify_gpu_service_health(max_retries=9):
            raise Exception("GPU service is not responding properly")

        # Step 3: Upload the audio file
        logger.info(f"Starting audio file upload for processing_id: {processing_id}")
        
        with record.original_file.open('rb') as file_handle:
            upload_response = requests.post(
                f"{GPU_SERVICE_URL}/upload",
                files={
                    'audio': (
                        os.path.basename(record.original_file.name),
                        file_handle,
                        'audio/mpeg'
                    )
                },
                headers={
                    'X-Api-Key': GPU_API_KEY,
                    'X-User-ID': str(record.user.id),
                    'X-Processing-ID': str(processing_id)
                },
                timeout=600  # 10 minute timeout for upload
            )
        
        upload_response.raise_for_status()
        upload_result = upload_response.json()
        
        logger.info(f"Audio upload completed successfully for processing_id: {processing_id}")
        return upload_result

    except Exception as exc:
        logger.error(f"Audio upload task failed for processing_id: {processing_id}, error: {str(exc)}")
        
        # Update record with error
        try:
            tool = Tool.objects.filter(name=TOOL_NAME).first()
            record = VoiceProcessing.objects.get(processing_id=processing_id, tool=tool)
            error_message = str(exc)[:97] + "..." if len(str(exc)) > 100 else str(exc)
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
        except:
            pass
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)

        
        # Determine retry strategy based on error type
        retry_count = self.request.retries
        
        if "VM failed to become active" in str(exc):
            countdown = 90  # Wait longer for VM issues
        elif "GPU service" in str(exc):
            countdown = min(30 * (retry_count + 1), 180)  # Exponential backoff, max 3 minutes
        else:
            countdown = min(60 * (2 ** retry_count), 300)  # Standard exponential backoff, max 5 minutes
        
        logger.info(f"Retrying audio upload task for processing_id: {processing_id} in {countdown} seconds (attempt {retry_count + 1})")
        raise self.retry(exc=exc, countdown=countdown)

@shared_task(bind=True, max_retries=2, time_limit=1200)  # 20 minutes  
def process_voice_task(self, upload_result, processing_id):
    """Process voice to text after successful upload"""
    
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VoiceProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting voice processing for processing_id: {processing_id}")
        
        # Update status
        record.status = 'PROCESSING'
        record.save()
        
        # Process voice with GPU service
        process_response = requests.post(
            f"{GPU_SERVICE_URL}/generate",
            json={
                'user_id': str(record.user.id),
                'language': record.target_language or 'en',
                'filename': upload_result.get('filename')
            },
            headers={
                'X-Api-Key': GPU_API_KEY,
                'X-User-ID': str(record.user.id),
                'Content-Type': 'application/json'
            },
            timeout=900  # 15 minute timeout for processing
        )
        
        process_response.raise_for_status()
        result_data = process_response.json()
        
        # Save the transcribed text
        text_data = TextToolData(content=result_data['text'])
        text_data.save()
        
        # Create usage history
        ToolUsageHistory.objects.create(
            user=record.user,
            tool=tool,
            additional_data_id=text_data.id
        )
        
        # Update record with result
        record.result_text_id = text_data.id
        record.result_text = result_data['text']
        record.status = 'COMPLETED'
        record.save()
        
        logger.info(f"Voice processing completed for processing_id: {processing_id}")
        
        # Update user usage
        update_usage(record.user, record.duration or 0, TOOL_NAME)
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)

        
        return {
            'status': 'completed',
            'processing_id': processing_id,
            'text': result_data['text'],
            'text_data_id': text_data.id
        }
        
    except Exception as exc:
        logger.error(f"Voice processing failed for processing_id: {processing_id}, error: {str(exc)}")
        
        # Update record with error
        try:
            tool = Tool.objects.filter(name=TOOL_NAME).first()
            record = VoiceProcessing.objects.get(processing_id=processing_id, tool=tool)
            error_message = str(exc)[:97] + "..." if len(str(exc)) > 100 else str(exc)
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
        except:
            pass
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)

        
        # Retry logic
        retry_count = self.request.retries
        countdown = min(120 * (retry_count + 1), 300)  # 2, 4, 5 minutes
        
        logger.info(f"Retrying voice processing for processing_id: {processing_id} in {countdown} seconds")
        raise self.retry(exc=exc, countdown=countdown)

def ensure_vm_is_active(record, processing_id,max_wait_minutes=30):
    """Ensure VM is active and ready for processing"""
    max_wait_seconds = max_wait_minutes * 60
    start_time = time.time()
    
    logger.info("Starting VM activation process...")
    
    # ALWAYS call /activate first to register this request
    try:
        activate_response = requests.post(
            f"{ORCHESTRATOR_URL}/activate",
            timeout=60,
            headers={
                "X-User-ID": str(record.user.email),
                "X-Processing-ID": str(processing_id),
                "X-Tool": "Voice to text"
            }
        )
        
        if activate_response.status_code == 200:
            activation_result = activate_response.json()
            activation_status = activation_result.get('status')
            
            logger.info(f"Initial activation response: {activation_result}")
            
            # If already active, we're potentially done
            if activation_status == 'ACTIVE':
                logger.info("VM is already active")
                # Still need to verify GPU service health below
            elif activation_status in ['RESTORING', 'HIBERNATING']:
                logger.info(f"VM is {activation_status.lower()}, will wait for completion...")
            else:
                logger.info(f"VM activation initiated, status: {activation_status}")
        else:
            logger.error(f"Failed to call /activate: {activate_response.status_code} - {activate_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error calling /activate: {str(e)}")
        return False
    
    # Now wait for VM to become active and healthy
    while time.time() - start_time < max_wait_seconds:
        try:
            # Check current orchestrator status
            status_response = requests.get(
                f"{ORCHESTRATOR_URL}/status",
                timeout=30,
                headers={
                    "X-User-ID": str(record.user.email),
                    "X-Processing-ID": str(processing_id),
                    "X-Tool": "Voice to text"
                }
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                current_status = status_data.get('status')
                gpu_healthy = status_data.get('gpu_service_healthy', False)
                
                logger.info(f"Current VM status: {current_status}, GPU healthy: {gpu_healthy}")
                
                # If active and healthy, we're done
                if current_status == 'ACTIVE' and gpu_healthy:
                    logger.info("VM is active and GPU service is healthy")
                    return True
                
                # If active but GPU service not healthy, wait
                elif current_status == 'ACTIVE' and not gpu_healthy:
                    logger.info("VM is active but GPU service not yet healthy, waiting...")
                    time.sleep(10)
                    continue
                
                # If still in transition states, wait
                elif current_status in ['RESTORING', 'HIBERNATING']:
                    logger.info(f"VM is {current_status.lower()}, waiting for completion...")
                    time.sleep(20)
                    continue
                
                # If went back to hibernated (shouldn't happen with pending requests)
                elif current_status == 'HIBERNATED':
                    logger.warning("VM went back to hibernated state unexpectedly")
                    time.sleep(15)
                    continue
                
                else:
                    logger.warning(f"Unexpected VM status: {current_status}")
            
            else:
                logger.error(f"Failed to get orchestrator status: {status_response.status_code}")
            
            # Standard wait before next check
            time.sleep(15)
            
        except requests.exceptions.Timeout:
            logger.warning("Timeout communicating with orchestrator, retrying...")
            time.sleep(10)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with orchestrator: {str(e)}")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error in ensure_vm_is_active: {str(e)}")
            time.sleep(10)
    
    logger.error(f"VM failed to become active within {max_wait_minutes} minutes")
    return False

def verify_gpu_service_health(max_retries=3):
    """Verify GPU service is responding properly"""
    logger.info("Verifying GPU service health...")
    
    for attempt in range(max_retries):
        try:
            health_response = requests.get(
                f"{GPU_SERVICE_URL}/health",
                timeout=15,
                headers={'X-Api-Key': GPU_API_KEY}
            )
            
            if health_response.status_code == 200:
                logger.info("GPU service health check passed")
                return True
            else:
                logger.warning(f"GPU service health check failed: {health_response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"GPU service health check attempt {attempt + 1} failed: {str(e)}")
            
        # Wait before retry (except on last attempt)
        if attempt < max_retries - 1:
            time.sleep(10)
    
    logger.error("GPU service failed all health checks")
    return False

def release_orchestrator_request(user_id, processing_id):
    """Release the orchestrator request"""
    try:
        release_response = requests.post(
            f"{ORCHESTRATOR_URL}/release",
            timeout=10,
            headers={
                "X-User-ID": str(user_id),
                "X-Processing-ID": str(processing_id),
                "X-Tool": "Voice to text"
            }
        )
        if release_response.status_code == 200:
            logger.info("Successfully released orchestrator request")
        else:
            logger.warning(f"Failed to release orchestrator request: {release_response.status_code}")
    except Exception as e:
        logger.error(f"Error releasing orchestrator request: {str(e)}")

def update_usage(user, duration, tool_name):
    """Update user's remaining trial time"""
    try:
        tool = Tool.objects.get(name=tool_name)
        usage, created = ToolUsage.objects.get_or_create(
            user=user,
            tool=tool,
            defaults={'max_trials': 300}  # Default 5 minutes
        )
        
        if not created:
            usage.max_trials = max(0, usage.max_trials - duration)
            usage.usage_count += duration
            usage.save()
            
        logger.info(f"Updated usage for user {user.id}, remaining: {usage.max_trials}")
        
    except Exception as e:
        logger.error(f"Usage update error: {str(e)}")

@shared_task
def cleanup_old_processing():
    """Clean up old processing records"""
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Starting cleanup of old voice processing records")
    
    # Delete records older than 7 days
    old_records = VoiceProcessing.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=7)
    )
    
    cleaned_count = 0
    for record in old_records:
        try:
            if record.original_file:
                record.original_file.delete(save=False)
            record.delete()
            cleaned_count += 1
        except Exception as e:
            logger.error(f"Error cleaning up record {record.id}: {str(e)}")
    
    logger.info(f"Cleaned up {cleaned_count} old voice processing records")
    return cleaned_count