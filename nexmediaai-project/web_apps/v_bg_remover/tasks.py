# v_bg_remover/tasks.py
import os
import time
import requests
import hashlib
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from loguru import logger
from core_apps.tools.models import Tool, ToolUsage
from .models import VideoProcessing

# Configuration
TOOL_NAME = "video-bg-remover"
GPU_SERVICE_URL = "http://149.36.1.159:5550"
ORCHESTRATOR_URL = "http://orchestrator:5550"
GPU_API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

@shared_task(
    bind=True,
    max_retries=0,               # no retries
    soft_time_limit=9000,        # 2.5 hours soft limit
    time_limit=9100              # hard limit slightly above
)
def upload_file_task(self, processing_id):
    """Upload file to GPU service with proper VM orchestration (no retry version)."""

    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VideoProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting upload task for processing_id: {processing_id}")

        # Step 0: Mark status as uploading
        record.status = 'UPLOADING'
        record.save()

        # Step 1: Ensure VM is active (wait full allowed time)
        logger.info(f"Ensuring VM is active for processing_id: {processing_id}")
        vm_activated = ensure_vm_is_active(record, processing_id, max_wait_minutes=30)
        if not vm_activated:
            raise Exception("VM failed to become active within timeout")

        # Step 2: Verify GPU service is healthy (few quick retries inside function)
        logger.info(f"Verifying GPU service health for processing_id: {processing_id}")
        if not verify_gpu_service_health(max_retries=9):
            raise Exception("GPU service is not responding properly")

        # Step 3: Upload the file
        logger.info(f"Starting file upload for processing_id: {processing_id}")
        with record.original_file.open('rb') as file_handle:
            upload_response = requests.post(
                f"{GPU_SERVICE_URL}/upload",
                files={
                    'file': (
                        os.path.basename(record.original_file.name),
                        file_handle,
                        'video/mp4'
                    )
                },
                headers={
                    'X-Api-Key': GPU_API_KEY,
                    'X-User-ID': str(record.user.id),
                    'X-Processing-ID': str(processing_id)
                },
                timeout=600  # 10 minute upload timeout
            )

        upload_response.raise_for_status()
        upload_result = upload_response.json()

        logger.info(f"Upload completed successfully for processing_id: {processing_id}")
        return upload_result

    except Exception as exc:
        logger.error(f"Upload task failed for processing_id: {processing_id}, error: {str(exc)}")

        # Update DB record as FAILED
        try:
            tool = Tool.objects.filter(name=TOOL_NAME).first()
            record = VideoProcessing.objects.get(processing_id=processing_id, tool=tool)
            error_message = str(exc)[:97] + "..." if len(str(exc)) > 100 else str(exc)
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
            logger.info(f"Updated record status to FAILED for processing_id: {processing_id}")
        except Exception as update_error:
            logger.error(f"Failed to update record status for processing_id: {processing_id}, error: {str(update_error)}")

        # Always release orchestrator request so VM can be freed
        release_orchestrator_request(user_id=record.user.email, processing_id=record.processing_id)


        # No retries — just exit
        return None

def ensure_vm_is_active(record, processing_id,max_wait_minutes=8):
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
                "X-Tool": "Video background remover"
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
                    "X-Tool": "Video background remover"
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
                "X-Tool": "Video background remover"
            }
        )
        if release_response.status_code == 200:
            logger.info("Successfully released orchestrator request")
        else:
            logger.warning(f"Failed to release orchestrator request: {release_response.status_code}")
    except Exception as e:
        logger.error(f"Error releasing orchestrator request: {str(e)}")

@shared_task(
    bind=True,
    max_retries=0,               # no retries
    soft_time_limit=9000,        # 2.5 hours soft limit
    time_limit=9100              # hard limit slightly above
)
def process_video_task(self, upload_result, processing_id):
    """Process video after successful upload"""
    
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VideoProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting video processing for processing_id: {processing_id}")
        
        # Update status
        record.status = 'PROCESSING'
        record.save()
        
        # Process video with GPU service
        process_response = requests.post(
            f"{GPU_SERVICE_URL}/process",
            json={
                'filename': upload_result['filename'],
                'user_id': str(record.user.id)
            },
            headers={'X-Api-Key': GPU_API_KEY},
            stream=True,
            timeout=3600  # 15 minute timeout for processing
        )
        
        process_response.raise_for_status()
        
        # Generate safe filename for processed video
        timestamp = int(time.time())
        filename_hash = hashlib.md5(upload_result['filename'].encode()).hexdigest()[:8]
        original_ext = os.path.splitext(upload_result['filename'])[1] or '.mp4'
        output_filename = f"proc_{processing_id}_{timestamp}_{filename_hash}{original_ext}"
        
        # Save processed video
        output_path = os.path.join(settings.MEDIA_ROOT, 'processed_videos', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as output_file:
            for chunk in process_response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)
        
        # Update record with result
        relative_path = os.path.join('processed_videos', output_filename)
        record.result_file = relative_path
        record.status = 'COMPLETED'
        record.save()
        
        logger.info(f"Video processing completed for processing_id: {processing_id}")
        
        # Update user usage
        update_usage(record.user, upload_result.get('duration', 0), 'video-bg-remover')
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=record.processing_id)

        
        return {
            'status': 'completed',
            'processing_id': processing_id,
            'result_file': relative_path
        }
        
    except Exception as exc:
        logger.error(f"Video processing failed for processing_id: {processing_id}, error: {str(exc)}")
        
        # Always update record with error and set status to FAILED
        try:
            tool = Tool.objects.filter(name=TOOL_NAME).first()
            record = VideoProcessing.objects.get(processing_id=processing_id, tool=tool)
            error_message = str(exc)[:97] + "..." if len(str(exc)) > 100 else str(exc)
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
            logger.info(f"Updated record status to FAILED for processing_id: {processing_id}")
        except Exception as update_error:
            logger.error(f"Failed to update record status for processing_id: {processing_id}, error: {str(update_error)}")
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=record.processing_id)

        
        # Retry logic
        retry_count = self.request.retries
        countdown = min(120 * (retry_count + 1), 300)  # 2, 4, 5 minutes
        
        logger.info(f"Retrying video processing for processing_id: {processing_id} in {countdown} seconds")
        raise self.retry(exc=exc, countdown=countdown)
    

def update_usage(user, duration, TOOL_NAME):
    """Update user's remaining trial time"""
    try:
        tool = Tool.objects.get(name=TOOL_NAME)
        usage, created = ToolUsage.objects.get_or_create(
            user=user,
            tool=tool,
            defaults={'max_trials': 180}  # Default 3 minutes
        )
        
        if not created:
            usage.max_trials = max(0, usage.max_trials - duration)
            usage.save()
            
        print(f"Updated usage for user {user.id}, remaining: {usage.max_trials}")
        
    except Exception as e:
        print(f"Usage update error: {str(e)}")

@shared_task
def cleanup_old_processing():
    """Clean up old processing records"""
    from django.utils import timezone
    from datetime import timedelta
    
    print("Starting cleanup of old processing records")
    
    # Delete records older than 7 days
    old_records = VideoProcessing.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=7)
    )
    
    cleaned_count = 0
    for record in old_records:
        try:
            if record.original_file:
                record.original_file.delete(save=False)
            if record.result_file:
                record.result_file.delete(save=False)
            record.delete()
            cleaned_count += 1
        except Exception as e:
            print(f"Error cleaning up record {record.id}: {str(e)}")
    
    print(f"Cleaned up {cleaned_count} old processing records")
    return cleaned_count

@shared_task
def handle_stuck_processes():
    """Handle processes that are stuck in UPLOADING or PROCESSING state for too long"""
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Checking for stuck processes")
    
    # Find processes stuck in UPLOADING for more than 30 minutes
    stuck_uploading = VideoProcessing.objects.filter(
        status='UPLOADING',
        updated_at__lt=timezone.now() - timedelta(minutes=30)
    )
    
    for record in stuck_uploading:
        logger.warning(f"Marking stuck UPLOADING process as failed: {record.processing_id}")
        record.status = 'FAILED'
        record.error_message = 'Process stuck in uploading state for too long'
        record.save()
    
    # Find processes stuck in PROCESSING for more than 60 minutes
    stuck_processing = VideoProcessing.objects.filter(
        status='PROCESSING',
        updated_at__lt=timezone.now() - timedelta(minutes=60)
    )
    
    for record in stuck_processing:
        logger.warning(f"Marking stuck PROCESSING process as failed: {record.processing_id}")
        record.status = 'FAILED'
        record.error_message = 'Process stuck in processing state for too long'
        record.save()
    
    total_stuck = len(stuck_uploading) + len(stuck_processing)
    if total_stuck > 0:
        logger.info(f"Marked {total_stuck} stuck processes as failed")
    
    return total_stuck