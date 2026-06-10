# video_caption tasks.py - FIXED VERSION
import os
import time
import requests
import hashlib
import signal
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, TimeLimitExceeded, SoftTimeLimitExceeded
from django.conf import settings
from loguru import logger
from core_apps.tools.models import Tool, ToolUsage
from .models import VideoCaptionProcessing

# Configuration
TOOL_NAME = "video-caption"
GPU_SERVICE_URL = "http://149.36.1.159:5005"  # Updated to correct port
ORCHESTRATOR_URL = "http://orchestrator:5550"
GPU_API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

# Custom timeout handler
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

# Enhanced task with better timeout handling and error recovery
@shared_task(bind=True, max_retries=2, soft_time_limit=3300, time_limit=3600, acks_late=True)  # 55min soft, 60min hard
def upload_file_task(self, processing_id):
    """Process video directly with GPU service using /process_direct endpoint"""
    tool = None
    record = None
    
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VideoCaptionProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting video processing task for processing_id: {processing_id}")
        
        # Update status to processing
        record.status = 'PROCESSING'
        record.save()

        # Step 1: Ensure VM is active and ready (with timeout)
        logger.info(f"Ensuring VM is active for processing_id: {processing_id}")
        
        # Set signal handler for VM activation timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1800)  # 30 minutes timeout for VM activation
        
        try:
            vm_activated = ensure_vm_is_active(record, processing_id, max_wait_minutes=25)  # Reduced from 30
            signal.alarm(0)  # Cancel timeout
            
            if not vm_activated:
                raise Exception("VM failed to become active within timeout")
        except TimeoutError:
            raise Exception("VM activation timed out")
        finally:
            signal.alarm(0)  # Ensure alarm is cancelled

        # Step 2: Verify GPU service is healthy
        logger.info(f"Verifying caption service health for processing_id: {processing_id}")
        if not verify_caption_service_health(max_retries=5):  # Reduced retries
            raise Exception("Caption service is not responding properly")

        # Step 3: Process the video with caption parameters
        logger.info(f"Starting video processing for processing_id: {processing_id}")
        
        # Get the actual file path
        file_path = record.original_file.path
        
        # Check file exists and is readable
        if not os.path.exists(file_path):
            raise Exception(f"Input file not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Processing file: {file_path} (size: {file_size / 1024 / 1024:.1f}MB)")
        
        # Prepare form data for caption service
        data = {
            'language': record.target_language,
            'font_family': record.font_family,
            'font_size': str(record.font_size),
            'font_color': record.font_color,
        }
        
        # Create session with connection pooling
        session = requests.Session()
        session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1))
        
        try:
            # Open the file and send to GPU service with progressive timeouts
            with open(file_path, 'rb') as file_handle:
                files = {
                    'video_file': (os.path.basename(file_path), file_handle, 'video/mp4')
                }
                
                logger.info(f"Sending video to GPU service for processing_id: {processing_id}")
                
                # Calculate timeout based on file size (minimum 600s, max 2700s)
                processing_timeout = min(max(600, file_size // (1024 * 1024) * 30), 2700)  # 30s per MB
                logger.info(f"Using processing timeout: {processing_timeout}s for file size: {file_size / 1024 / 1024:.1f}MB")
                
                response = session.post(
                    f"{GPU_SERVICE_URL}/process_direct",
                    files=files,
                    data=data,
                    headers={
                        'X-Api-Key': GPU_API_KEY,
                        'X-User-ID': str(record.user.id),
                        'X-Processing-ID': str(processing_id)
                    },
                    stream=True,
                    timeout=(30, processing_timeout)  # (connection, read) timeout
                )
        finally:
            session.close()
        
        if response.status_code != 200:
            error_text = response.text[:500] if hasattr(response, 'text') else 'Unknown error'
            raise Exception(f"GPU service error {response.status_code}: {error_text}")
        
        logger.info(f"GPU service completed processing for processing_id: {processing_id}")
        
        # Get video duration from response headers
        video_duration = response.headers.get('X-Video-Duration-Seconds', '0')
        try:
            duration_seconds = int(float(video_duration))
        except (ValueError, TypeError):
            duration_seconds = 0
            
        # Generate safe filename for processed video
        timestamp = int(time.time())
        filename_hash = hashlib.md5(record.original_file.name.encode()).hexdigest()[:8]
        original_ext = os.path.splitext(record.original_file.name)[1] or '.mp4'
        output_filename = f"captioned_{processing_id}_{timestamp}_{filename_hash}{original_ext}"
        output_path = os.path.join(settings.MEDIA_ROOT, 'processed_captioned_videos', output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save processed video with progress tracking
        logger.info(f"Saving processed video for processing_id: {processing_id}")
        bytes_downloaded = 0
        content_length = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as output_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    output_file.write(chunk)
                    bytes_downloaded += len(chunk)
                    
                    # Log progress every 10MB
                    if content_length > 0 and bytes_downloaded % (10 * 1024 * 1024) == 0:
                        progress = (bytes_downloaded / content_length) * 100
                        logger.info(f"Download progress for {processing_id}: {progress:.1f}%")
        
        logger.info(f"Saved {bytes_downloaded / 1024 / 1024:.1f}MB to {output_path}")
        
        # Verify output file was created properly
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Output file was not created properly or is empty")
        
        # Update record with result
        relative_path = os.path.join('processed_captioned_videos', output_filename)
        record.result_file = relative_path
        record.status = 'COMPLETED'
        record.video_duration = duration_seconds
        record.save()
        
        logger.info(f"Video processing completed for processing_id: {processing_id}")
        
        # Update user usage
        update_usage(record.user, duration_seconds, TOOL_NAME)
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)
        
        return {
            'status': 'completed',
            'processing_id': processing_id,
            'result_file': relative_path,
            'duration': duration_seconds,
            'output_size_mb': os.path.getsize(output_path) / 1024 / 1024
        }
        
    except SoftTimeLimitExceeded:
        logger.error(f"Soft time limit exceeded for processing_id: {processing_id}")
        error_message = "Processing took too long (soft timeout)"
        handle_task_failure(record, error_message, release_request=True)
        raise  # Don't retry on soft timeout
        
    except TimeLimitExceeded:
        logger.error(f"Hard time limit exceeded for processing_id: {processing_id}")
        error_message = "Processing took too long (hard timeout)"
        handle_task_failure(record, error_message, release_request=True)
        raise  # Don't retry on hard timeout
        
    except Exception as exc:
        logger.error(f"Video processing failed for processing_id: {processing_id}, error: {str(exc)}")
        
        # Handle specific error types
        is_retryable = is_error_retryable(exc)
        error_message = str(exc)[:97] + "..." if len(str(exc)) > 100 else str(exc)
        
        # Update record with error
        handle_task_failure(record, error_message, release_request=True)
        
        # Retry logic - only retry certain types of errors
        if is_retryable and self.request.retries < self.max_retries:
            retry_count = self.request.retries
            countdown = min(60 * (retry_count + 1), 180)  # 60s, 120s, 180s
            
            logger.info(f"Retrying video processing for processing_id: {processing_id} in {countdown} seconds (attempt {retry_count + 1})")
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error(f"Not retrying for processing_id: {processing_id}. Retryable: {is_retryable}, Retries: {self.request.retries}/{self.max_retries}")
            raise exc

def is_error_retryable(exc):
    """Determine if an error is worth retrying"""
    error_str = str(exc).lower()
    
    # Don't retry these errors
    non_retryable_errors = [
        'file not found',
        'invalid video file',
        'file too large',
        'video too long',
        'unauthorized',
        'invalid api key',
        'soft timeout',
        'hard timeout',
        'empty',
        'corrupted',
        'format not supported'
    ]
    
    for non_retryable in non_retryable_errors:
        if non_retryable in error_str:
            return False
    
    # Retry these errors
    retryable_errors = [
        'connection',
        'timeout',
        'service not responding',
        'vm failed to become active',
        'gpu service error 5',  # 5xx errors
        'internal server error',
        'service unavailable',
        'gateway timeout'
    ]
    
    for retryable in retryable_errors:
        if retryable in error_str:
            return True
    
    # Default: don't retry unknown errors
    return False

def handle_task_failure(record, error_message, release_request=True):
    """Handle task failure consistently"""
    try:
        if record:
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
            logger.info(f"Updated record {record.processing_id} with error: {error_message}")
    except Exception as e:
        logger.error(f"Error updating record: {str(e)}")
    
    if release_request:
        release_orchestrator_request(user_id=record.user.email, processing_id=record.processing_id)

def ensure_vm_is_active(record, processing_id, max_wait_minutes=30):  # Reduced from 30
    """Ensure VM is active and ready for processing"""
    max_wait_seconds = max_wait_minutes * 60
    start_time = time.time()
    last_status_log = 0
    
    logger.info("Starting VM activation process...")
    
    # ALWAYS call /activate first to register this request
    try:
        activate_response = requests.post(
            f"{ORCHESTRATOR_URL}/activate",
            timeout=60,
            headers={
                "X-User-ID": str(record.user.email),
                "X-Processing-ID": str(processing_id),
                "X-Tool": "Video Caption"
            }
        )
        
        if activate_response.status_code == 200:
            activation_result = activate_response.json()
            activation_status = activation_result.get('status')
            
            logger.info(f"Initial activation response: {activation_result}")
            
            # If already active, we're potentially done
            if activation_status == 'ACTIVE':
                logger.info("VM is already active")
                # Still need to verify service health below
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
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    while time.time() - start_time < max_wait_seconds:
        try:
            status_response = requests.get(
                f"{ORCHESTRATOR_URL}/status",
                timeout=30,
                headers={
                    "X-User-ID": str(record.user.email),
                    "X-Processing-ID": str(processing_id),
                    "X-Tool": "Video Caption"
                }
            )
            
            if status_response.status_code == 200:
                consecutive_failures = 0  # Reset failure counter
                status_data = status_response.json()
                current_status = status_data.get('status')
                service_healthy = status_data.get('gpu_service_healthy', False)
                
                # Log status every 30 seconds to avoid spam
                current_time = time.time()
                if current_time - last_status_log > 30:
                    logger.info(f"Current VM status: {current_status}, GPU service healthy: {service_healthy}")
                    logger.info(f"Elapsed time: {current_time - start_time:.0f}s / {max_wait_seconds}s")
                    last_status_log = current_time
                
                # If active and healthy, we're done
                if current_status == 'ACTIVE' and service_healthy:
                    logger.info("VM is active and GPU service is healthy")
                    return True
                
                # If active but service not healthy, wait a bit more
                elif current_status == 'ACTIVE' and not service_healthy:
                    logger.info("VM is active but GPU service not yet healthy, waiting...")
                    time.sleep(10)
                    continue
                
                # If still in transition states, wait
                elif current_status in ['RESTORING', 'HIBERNATING']:
                    time.sleep(15)
                    continue
                
                # If went back to hibernated (shouldn't happen with pending requests)
                elif current_status == 'HIBERNATED':
                    logger.warning("VM went back to hibernated state unexpectedly, re-activating...")
                    # Try to re-activate
                    try:
                        requests.post(f"{ORCHESTRATOR_URL}/activate", timeout=30)
                    except:
                        pass
                    time.sleep(15)
                    continue
                
                else:
                    logger.warning(f"Unexpected VM status: {current_status}")
            
            else:
                consecutive_failures += 1
                logger.error(f"Failed to get orchestrator status: {status_response.status_code}")
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"Too many consecutive failures ({consecutive_failures}), giving up")
                    return False
            
            # Standard wait before next check
            time.sleep(10)
            
        except requests.exceptions.Timeout:
            consecutive_failures += 1
            logger.warning(f"Timeout communicating with orchestrator (failure {consecutive_failures}/{max_consecutive_failures})")
            if consecutive_failures >= max_consecutive_failures:
                return False
            time.sleep(10)
            
        except requests.exceptions.RequestException as e:
            consecutive_failures += 1
            logger.error(f"Error communicating with orchestrator: {str(e)} (failure {consecutive_failures}/{max_consecutive_failures})")
            if consecutive_failures >= max_consecutive_failures:
                return False
            time.sleep(10)
            
        except Exception as e:
            logger.error(f"Unexpected error in ensure_vm_is_active: {str(e)}")
            time.sleep(10)
    
    logger.error(f"VM failed to become active within {max_wait_minutes} minutes")
    return False

def verify_caption_service_health(max_retries=5):  # Reduced from 12
    """Verify caption service is responding properly"""
    logger.info("Verifying caption service health...")
    
    for attempt in range(max_retries):
        try:
            health_response = requests.get(
                f"{GPU_SERVICE_URL}/health",
                timeout=15,
                headers={'X-Api-Key': GPU_API_KEY}
            )
            
            if health_response.status_code == 200:
                health_data = health_response.json()
                logger.info(f"Caption service health check passed: {health_data}")
                return True
            else:
                logger.warning(f"Caption service health check failed: {health_response.status_code} - {health_response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Caption service health check attempt {attempt + 1} failed: {str(e)}")
            
        # Wait before retry (except on last attempt)
        if attempt < max_retries - 1:
            time.sleep(8)  # Reduced from 10
    
    logger.error("Caption service failed all health checks")
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
                "X-Tool": "Video Caption"
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
            usage.save()
            
        logger.info(f"Updated usage for user {user.id}, remaining: {usage.max_trials}")
        
    except Exception as e:
        logger.error(f"Usage update error: {str(e)}")

@shared_task
def cleanup_old_processing():
    """Clean up old processing records"""
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Starting cleanup of old caption processing records")
    
    # Delete records older than 7 days
    old_records = VideoCaptionProcessing.objects.filter(
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
            logger.error(f"Error cleaning up record {record.id}: {str(e)}")
    
    logger.info(f"Cleaned up {cleaned_count} old caption processing records")
    return cleaned_count

# New debugging task
@shared_task
def debug_stuck_task(processing_id):
    """Debug a specific stuck task"""
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = VideoCaptionProcessing.objects.get(processing_id=processing_id, tool=tool)
        
        logger.info(f"Debug info for processing_id: {processing_id}")
        logger.info(f"Status: {record.status}")
        logger.info(f"Created: {record.created_at}")
        logger.info(f"Updated: {record.updated_at}")
        logger.info(f"Error: {record.error_message}")
        
        # Check if file exists
        if record.original_file:
            file_path = record.original_file.path
            logger.info(f"Original file exists: {os.path.exists(file_path)}")
            if os.path.exists(file_path):
                logger.info(f"File size: {os.path.getsize(file_path)} bytes")
        
        if record.result_file:
            result_path = record.result_file.path
            logger.info(f"Result file exists: {os.path.exists(result_path)}")
            if os.path.exists(result_path):
                logger.info(f"Result file size: {os.path.getsize(result_path)} bytes")
        
        return {
            'processing_id': str(processing_id),
            'status': record.status,
            'error': record.error_message
        }
        
    except Exception as e:
        logger.error(f"Debug task error: {str(e)}")
        return {'error': str(e)}

@shared_task
def handle_stuck_processes():
    """Handle processes that are stuck in UPLOADING or PROCESSING state for too long"""
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Checking for stuck video caption processes")
    
    # Find processes stuck in UPLOADING for more than 30 minutes
    stuck_uploading = VideoCaptionProcessing.objects.filter(
        status='UPLOADING',
        updated_at__lt=timezone.now() - timedelta(minutes=30)
    )
    
    for record in stuck_uploading:
        logger.warning(f"Marking stuck UPLOADING process as failed: {record.processing_id}")
        record.status = 'FAILED'
        record.error_message = 'Process stuck in uploading state for too long'
        record.save()
    
    # Find processes stuck in PROCESSING for more than 60 minutes
    stuck_processing = VideoCaptionProcessing.objects.filter(
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
        logger.info(f"Marked {total_stuck} stuck video caption processes as failed")
    
    return total_stuck