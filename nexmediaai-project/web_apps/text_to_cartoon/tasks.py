# text_to_cartoon/tasks.py
import os
import time
import uuid
import requests
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from loguru import logger
from core_apps.tools.models import Tool, ToolUsage, ToolUsageHistory
from core_apps.tool_data.models import FileToolData
from .models import CartoonProcessing

# Configuration
TOOL_NAME = "text-to-cartoon"
GPU_SERVICE_URL = "http://149.36.1.159:5004"  # Cartoon generation service
ORCHESTRATOR_URL = "http://orchestrator:5550"
GPU_API_KEY = "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"

@shared_task(bind=True, soft_time_limit=7200, time_limit=7500)
def process_cartoon_task(self, processing_id):
    """Process cartoon generation"""
    
    try:
        tool = Tool.objects.filter(name=TOOL_NAME).first()
        record = CartoonProcessing.objects.get(processing_id=processing_id, tool=tool)
        logger.info(f"Starting cartoon processing for processing_id: {processing_id}")
        
        # Update status to processing
        record.status = 'PROCESSING'
        record.save()
        
        # Step 1: Ensure VM is active and ready
        logger.info(f"Ensuring VM is active for processing_id: {processing_id}")
        
        vm_activated = ensure_vm_is_active(record, processing_id, max_wait_minutes=30)
        if not vm_activated:
            raise Exception("VM failed to become active within timeout")

        # Step 2: Verify GPU service is healthy
        logger.info(f"Verifying GPU service health for processing_id: {processing_id}")
        
        if not verify_gpu_service_health(max_retries=9):
            raise Exception("GPU service is not responding properly")

        # Step 3: Generate the cartoon
        logger.info(f"Starting cartoon generation for processing_id: {processing_id}")
        
        generation_response = requests.post(
            f"{GPU_SERVICE_URL}/generate",
            json={
                'prompt': record.prompt
            },
            timeout=900  # 15 minute timeout for generation
        )
        
        generation_response.raise_for_status()
        
        # Save the generated image
        filename = f"{record.user.id}_{uuid.uuid4().hex[:8]}.png"
        file_path = os.path.join(settings.MEDIA_ROOT, "cartoon_results", filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(generation_response.content)
        
        # Save file data
        file_data = FileToolData.objects.create(
            user=record.user,                     # required
            file_name=filename,                   # match model's field name
            file_path=file_path                   # match model's field name
        )
        
        # Update record with result
        record.result_image.name = os.path.join("cartoon_results", filename)
        record.result_image_id = file_data.id
        record.status = 'COMPLETED'
        record.save()
        
        # Create usage history
        ToolUsageHistory.objects.create(
            user=record.user,
            tool=tool,
            additional_data_id=file_data.id
        )
        
        logger.info(f"Cartoon generation completed for processing_id: {processing_id}")
        
        # Update user usage
        update_usage(record.user, 1, TOOL_NAME)
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)
        
        return {
            'status': 'completed',
            'processing_id': processing_id,
            'image_path': file_path,
            'file_data_id': file_data.id
        }
        
    except Exception as exc:
        logger.error(f"Cartoon generation failed for processing_id: {processing_id}, error: {str(exc)}")
        
        # Update record with error
        try:
            tool = Tool.objects.filter(name=TOOL_NAME).first()
            record = CartoonProcessing.objects.get(processing_id=processing_id, tool=tool)
            error_message = str(exc)[:497] + "..." if len(str(exc)) > 500 else str(exc)
            record.status = 'FAILED'
            record.error_message = error_message
            record.save()
        except:
            pass
        
        # Release orchestrator request
        release_orchestrator_request(user_id=record.user.email, processing_id=processing_id)

        
        
        raise  

def ensure_vm_is_active(record, processing_id, max_wait_minutes=30):
    """Ensure VM is active and ready for processing"""
    max_wait_seconds = max_wait_minutes * 60
    start_time = time.time()
    
    logger.info("Starting VM activation process...")
    
    # ALWAYS call /activate first to register this request
    try:
        # Inside ensure_vm_is_active()

        activate_response = requests.post(
            f"{ORCHESTRATOR_URL}/activate",
            timeout=60,
            headers={
                "X-User-ID": str(record.user.email),
                "X-Processing-ID": str(processing_id),
                "X-Tool": "Text to cartoon"
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
                    "X-Tool": "Text to cartoon"
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
                "X-Tool": "Text to cartoon"
            }
        )
        if release_response.status_code == 200:
            logger.info("Successfully released orchestrator request")
        else:
            logger.warning(f"Failed to release orchestrator request: {release_response.status_code}")
    except Exception as e:
        logger.error(f"Error releasing orchestrator request: {str(e)}")

def update_usage(user, usage_amount, tool_name):
    """Update user's remaining trials"""
    try:
        tool = Tool.objects.get(name=tool_name)
        usage, created = ToolUsage.objects.get_or_create(
            user=user,
            tool=tool,
            defaults={'max_trials': 5}  # Default 5 trials
        )
        
        if not created:
            usage.max_trials = max(0, usage.max_trials - usage_amount)
            usage.usage_count += usage_amount
            usage.save()
            
        logger.info(f"Updated usage for user {user.id}, remaining: {usage.max_trials}")
        
    except Exception as e:
        logger.error(f"Usage update error: {str(e)}")

@shared_task
def cleanup_old_processing():
    """Clean up old processing records"""
    from django.utils import timezone
    from datetime import timedelta
    
    logger.info("Starting cleanup of old cartoon processing records")
    
    # Delete records older than 7 days
    old_records = CartoonProcessing.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=7)
    )
    
    cleaned_count = 0
    for record in old_records:
        try:
            if record.result_image:
                record.result_image.delete(save=False)
            record.delete()
            cleaned_count += 1
        except Exception as e:
            logger.error(f"Error cleaning up record {record.id}: {str(e)}")
    
    logger.info(f"Cleaned up {cleaned_count} old cartoon processing records")
    return cleaned_count