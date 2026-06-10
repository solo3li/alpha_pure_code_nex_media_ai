# Enhanced Orchestrator for managing VM state with Hyperstack API and Redis
import os
import time
import threading
import requests
from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash
import redis
from datetime import datetime, timedelta
import logging
import json
from collections import defaultdict
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here-change-this')
logging.basicConfig(level=logging.INFO)

# Configuration
HYPERSTACK_API = os.getenv('HYPERSTACK_API', 'https://infrahub-api.nexgencloud.com/v1')
VM_ID = os.getenv('VM_ID', '305668')
API_KEY = os.getenv('HYPERSTACK_API_KEY', 'ce187658-55e4-464d-9df4-0e39cd5a5f9b')
IDLE_TIMEOUT = int(os.getenv('IDLE_TIMEOUT', 600))  # 2 minutes in seconds
VM_IP = os.getenv('VM_IP', '149.36.1.159')
GPU_SERVICE_PORT = os.getenv('GPU_SERVICE_PORT', '5550')

# Dashboard login credentials (hardcoded for now)
DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'admin123')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'asfgbadfhybsdfxgvadrv')
REDIS_DB = int(os.getenv('REDIS_DB', 0))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True
)

def require_auth(f):
    """Decorator to require authentication for dashboard routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for dashboard access"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == DASHBOARD_PASSWORD:
            session['authenticated'] = True
            session.permanent = True  # Make session permanent
            app.permanent_session_lifetime = timedelta(hours=24)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Replace the initialize_state function with this enhanced version
def initialize_state():
    """Initialize VM state in Redis with proper validation"""
    if not r.exists('vm_state'):
        # Full initialization if state doesn't exist
        state_data = {
            'status': 'HIBERNATED',
            'last_activity': 0,
            'last_operation': 0,
            'pending_requests': 0,
            'operation_start_time': 0,
            'last_health_check': 0,
            'webhook_events': 0,
            'restore_after_hibernation': 0,
            'hibernation_requested': 0,
            'user_activity_time': 0,
            'restore_retry_count': 0,
            'last_restore_attempt': 0,
            'hibernation_complete_time': 0
        }
        r.hmset('vm_state', state_data)
        print("Initialized VM state as HIBERNATED")
    else:
        # Check if critical fields are missing and restore them
        current_fields = r.hkeys('vm_state')
        required_fields = ['status', 'last_activity', 'last_operation', 'pending_requests',
                          'operation_start_time', 'user_activity_time']
        
        missing_fields = [field for field in required_fields if field not in current_fields]
        
        if missing_fields:
            print(f"Warning: Missing fields in VM state: {missing_fields}. Repairing...")
            repair_data = {}
            
            if 'status' not in current_fields:
                # Try to determine actual state
                if check_gpu_service_health():
                    repair_data['status'] = 'ACTIVE'
                    repair_data['user_activity_time'] = time.time()
                else:
                    repair_data['status'] = 'HIBERNATED'
            
            # Set defaults for other missing fields
            defaults = {
                'last_activity': 0,
                'last_operation': 0,
                'pending_requests': 0,
                'operation_start_time': 0,
                'user_activity_time': 0,
                'restore_retry_count': 0,
                'last_restore_attempt': 0,
                'hibernation_complete_time': 0
            }
            
            for field in missing_fields:
                if field not in repair_data and field in defaults:
                    repair_data[field] = defaults[field]
            
            if repair_data:
                r.hmset('vm_state', repair_data)
                print(f"Repaired VM state with: {repair_data}")

# Add this function to help with state recovery
def recover_vm_state():
    """Attempt to recover VM state by checking actual VM status"""
    print("Attempting VM state recovery...")
    
    # Check if GPU service is accessible
    if check_gpu_service_health():
        print("GPU service is healthy - setting state to ACTIVE")
        r.hmset('vm_state', {
            'status': 'ACTIVE',
            'user_activity_time': time.time(),
            'last_operation': time.time(),
            'pending_requests': 0
        })
        return 'ACTIVE'
    else:
        print("GPU service is not accessible - setting state to HIBERNATED")
        r.hmset('vm_state', {
            'status': 'HIBERNATED',
            'last_operation': time.time(),
            'pending_requests': 0,
            'user_activity_time': 0
        })
        return 'HIBERNATED'

def store_action_log(action_type, user_id, details, status='success'):
    """Store action logs persistently with expiration"""
    try:
        current_time = time.time()
        action_data = {
            'timestamp': current_time,
            'action_type': action_type,
            'user_id': user_id,
            'details': details,
            'status': status,
            'formatted_time': datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Store in Redis list (keep last 1000 actions)
        r.lpush('action_logs', json.dumps(action_data))
        r.ltrim('action_logs', 0, 999)  # Keep only last 1000 actions
        
        # Also store in daily log for long-term storage
        daily_key = f"daily_actions:{datetime.fromtimestamp(current_time).strftime('%Y-%m-%d')}"
        r.lpush(daily_key, json.dumps(action_data))
        r.expire(daily_key, 86400 * 30)  # Keep daily logs for 30 days
        
        print(f"Stored action log: {action_type} by {user_id}")
        
    except Exception as e:
        print(f"Error storing action log: {str(e)}")

def get_action_logs(limit=100, days_back=7):
    """Get action logs with optional filtering"""
    try:
        logs = []
        
        # Get recent logs from main list
        recent_logs_raw = r.lrange('action_logs', 0, limit - 1)
        for log_data in recent_logs_raw:
            try:
                log_info = json.loads(log_data)
                logs.append(log_info)
            except:
                continue
        
        # If we need more logs, check daily logs
        if len(logs) < limit and days_back > 0:
            current_date = datetime.now()
            for day in range(days_back):
                check_date = current_date - timedelta(days=day)
                daily_key = f"daily_actions:{check_date.strftime('%Y-%m-%d')}"
                daily_logs_raw = r.lrange(daily_key, 0, -1)
                
                for log_data in daily_logs_raw:
                    try:
                        log_info = json.loads(log_data)
                        if log_info not in logs:  # Avoid duplicates
                            logs.append(log_info)
                            if len(logs) >= limit:
                                break
                    except:
                        continue
                
                if len(logs) >= limit:
                    break
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return logs[:limit]
        
    except Exception as e:
        print(f"Error getting action logs: {str(e)}")
        return []

def track_user_request(user_id, request_type, tool=None, processing_id=None, email=None):
    """Track user requests and activity with persistent storage"""
    try:
        current_time = time.time()
        user_key = f"user:{user_id}"
        
        # Get existing user data
        existing_data = r.hgetall(user_key)
        total_requests = int(existing_data.get('total_requests', 0)) + 1
        
        # Store user info with email if provided
        user_data = {
            'user_id': user_id,
            'last_activity': current_time,
            'total_requests': total_requests,
            'last_request_type': request_type,
            'last_processing_id': processing_id or '',
            'first_seen': existing_data.get('first_seen', current_time),
            'email': email or existing_data.get('email', ''),
            'total_sessions': int(existing_data.get('total_sessions', 1))
        }
        
        r.hmset(user_key, user_data)
        
        # Add to user request history (keep last 200 requests)
        request_data = {
            'timestamp': current_time,
            'type': request_type,
            'processing_id': processing_id or '',
            'user_id': user_id,
            'tool': tool,
            'email': email or existing_data.get('email', '')
        }
        r.lpush('user_requests_history', json.dumps(request_data))
        r.ltrim('user_requests_history', 0, 199)  # Keep only last 200 requests
        
        # Track active users (expire after 2 hours of inactivity)
        r.sadd('active_users', user_id)
        r.expire('active_users', 7200)
        
        # Set user-specific expiration (longer for persistent storage)
        r.expire(user_key, 86400 * 30)  # User data expires after 30 days of inactivity
        
        # Store action log
        store_action_log(
            action_type=f'user_request_{request_type}',
            user_id=user_id,
            details=f"Tool: {tool}, Processing ID: {processing_id}, Email: {email or 'N/A'}"
        )
        
        print(f"Tracked request from user {user_id}: {request_type}")
        
    except Exception as e:
        print(f"Error tracking user request: {str(e)}")

def get_user_stats(search_email=None, limit=50):
    """Get statistics about users and their requests with email search"""
    try:
        stats = {
            'active_users': [],
            'total_active_users': 0,
            'recent_requests': [],
            'user_summary': {},
            'total_users_ever': 0,
            'search_results': []
        }
        
        # Get active users
        active_user_ids = r.smembers('active_users')
        stats['total_active_users'] = len(active_user_ids)
        
        # Get detailed info for each active user
        for user_id in active_user_ids:
            user_key = f"user:{user_id}"
            user_data = r.hgetall(user_key)
            if user_data:
                user_info = {
                    'user_id': user_id,
                    'email': user_data.get('email', 'N/A'),
                    'last_activity': float(user_data.get('last_activity', 0)),
                    'total_requests': int(user_data.get('total_requests', 0)),
                    'last_request_type': user_data.get('last_request_type', ''),
                    'last_processing_id': user_data.get('last_processing_id', ''),
                    'time_since_activity': time.time() - float(user_data.get('last_activity', 0)),
                    'first_seen': float(user_data.get('first_seen', 0)),
                    'total_sessions': int(user_data.get('total_sessions', 1))
                }
                stats['active_users'].append(user_info)
        
        # Sort by most recent activity
        stats['active_users'].sort(key=lambda x: x['last_activity'], reverse=True)
        
        # Email search functionality
        if search_email:
            search_results = []
            # Search through all user keys
            user_keys = r.keys('user:*')
            for user_key in user_keys:
                user_data = r.hgetall(user_key)
                user_email = user_data.get('email', '').lower()
                if search_email.lower() in user_email and user_email:
                    user_info = {
                        'user_id': user_key.replace('user:', ''),
                        'email': user_data.get('email', 'N/A'),
                        'last_activity': float(user_data.get('last_activity', 0)),
                        'total_requests': int(user_data.get('total_requests', 0)),
                        'first_seen': float(user_data.get('first_seen', 0)),
                        'time_since_activity': time.time() - float(user_data.get('last_activity', 0))
                    }
                    search_results.append(user_info)
            
            search_results.sort(key=lambda x: x['last_activity'], reverse=True)
            stats['search_results'] = search_results[:limit]
        
        # Get recent request history
        recent_requests_raw = r.lrange('user_requests_history', 0, limit - 1)
        for req_data in recent_requests_raw:
            try:
                req_info = json.loads(req_data)
                req_info['time_ago'] = time.time() - req_info['timestamp']
                stats['recent_requests'].append(req_info)
            except:
                continue
        
        # Generate user summary
        user_request_counts = defaultdict(int)
        for req in stats['recent_requests']:
            user_request_counts[req['user_id']] += 1
        
        stats['user_summary'] = dict(user_request_counts)
        
        # Count total users ever
        all_user_keys = r.keys('user:*')
        stats['total_users_ever'] = len(all_user_keys)
        
        return stats
        
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        return {
            'active_users': [],
            'total_active_users': 0,
            'recent_requests': [],
            'user_summary': {},
            'total_users_ever': 0,
            'search_results': []
        }

def check_gpu_service_health():
    """Check if GPU service is responding"""
    try:
        response = requests.get(
            f"http://{VM_IP}:{GPU_SERVICE_PORT}/health", 
            timeout=10,
            headers={'X-Api-Key': "GPukTcc2FXcAo32U6j6y5rOK8LJW5QAf"}
        )
        is_healthy = response.status_code == 200
        
        # Update last health check time
        r.hset('vm_state', 'last_health_check', time.time())
        
        # Store action log for health checks
        store_action_log(
            action_type='health_check',
            user_id='system',
            details=f"Status: {response.status_code}, Healthy: {is_healthy}"
        )
        
        print(f"GPU service health check: {'PASS' if is_healthy else 'FAIL'} (status: {response.status_code})")
        return is_healthy
        
    except requests.exceptions.RequestException as e:
        store_action_log(
            action_type='health_check',
            user_id='system',
            details=f"Failed: {str(e)}",
            status='error'
        )
        print(f"GPU service health check failed: {str(e)}")
        return False

def call_hyperstack_api(endpoint, method='POST'):
    """Make API call to Hyperstack with proper error handling"""
    try:
        url = f"{HYPERSTACK_API}/core/virtual-machines/{VM_ID}/{endpoint}"
        headers = {'api_key': API_KEY}
        
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Hyperstack API {method} {endpoint}: {response.status_code} - {response.text}")
        
        # Store API call log
        store_action_log(
            action_type=f'hyperstack_api_{endpoint}',
            user_id='system',
            details=f"Status: {response.status_code}, Response: {response.text[:200]}",
            status='success' if response.status_code == 200 else 'error'
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Hyperstack API error: {response.status_code} - {response.text}")
            return {'status': False, 'error': response.text, 'status_code': response.status_code}
            
    except requests.exceptions.RequestException as e:
        store_action_log(
            action_type=f'hyperstack_api_{endpoint}',
            user_id='system',
            details=f"Request failed: {str(e)}",
            status='error'
        )
        print(f"Hyperstack API call failed: {str(e)}")
        return {'status': False, 'error': str(e)}

def determine_actual_vm_state():
    """Determine actual VM state based on health check and Redis state"""
    current_redis_state = r.hget('vm_state', 'status') or 'HIBERNATED'
    
    # If Redis says it's in transition, we should trust webhooks to update it
    # Don't override transition states with health checks
    if current_redis_state in ['HIBERNATING', 'RESTORING']:
        return current_redis_state
    
    # If Redis says HIBERNATED, check if we can actually reach the service
    if current_redis_state == 'HIBERNATED':
        if check_gpu_service_health():
            # Service is responding but Redis thinks it's hibernated - update Redis
            print("Service is healthy but Redis state was HIBERNATED - correcting to ACTIVE")
            store_action_log(
                action_type='state_correction',
                user_id='system',
                details='Corrected HIBERNATED to ACTIVE based on health check'
            )
            return 'ACTIVE'
        else:
            # Service not responding, likely still hibernated
            return 'HIBERNATED'
    
    # If Redis says ACTIVE, verify with health check
    if current_redis_state == 'ACTIVE':
        if check_gpu_service_health():
            return 'ACTIVE'
        else:
            # Service not responding but Redis thinks it's active
            # This could mean it just became hibernated
            store_action_log(
                action_type='state_correction',
                user_id='system',
                details='Corrected ACTIVE to HIBERNATED based on failed health check'
            )
            return 'HIBERNATED'
    
    return current_redis_state

def sync_redis_with_actual_state():
    """Synchronize Redis state with actual VM state"""
    actual_state = determine_actual_vm_state()
    current_redis_state = r.hget('vm_state', 'status') or 'HIBERNATED'
    
    print(f"State sync - Redis: {current_redis_state}, Determined: {actual_state}")
    
    # Only update Redis if there's a definitive state change
    # Don't override transition states unless we're very sure
    if (actual_state != current_redis_state and 
        actual_state in ['ACTIVE', 'HIBERNATED'] and
        current_redis_state not in ['HIBERNATING', 'RESTORING']):
        
        r.hset('vm_state', 'status', actual_state)
        r.hset('vm_state', 'last_operation', time.time())
        
        # Only update user_activity_time if we're transitioning TO active
        # Don't update it just because we detected the VM is active
        if actual_state == 'ACTIVE' and current_redis_state != 'ACTIVE':
            user_activity_time = float(r.hget('vm_state', 'user_activity_time') or 0)
            if user_activity_time == 0:  # Only set if not already set
                r.hset('vm_state', 'user_activity_time', time.time())
        
        store_action_log(
            action_type='state_sync',
            user_id='system',
            details=f'Synced state from {current_redis_state} to {actual_state}'
        )
        print(f"Updated Redis state from {current_redis_state} to {actual_state}")

def attempt_restore_vm():
    """Attempt to restore VM with proper error handling and retries"""
    try:
        current_time = time.time()
        vm_data = r.hgetall('vm_state')
        
        restore_retry_count = int(vm_data.get('restore_retry_count', 0))
        last_restore_attempt = float(vm_data.get('last_restore_attempt', 0))
        hibernation_complete_time = float(vm_data.get('hibernation_complete_time', 0))
        
        # Check if we should wait before attempting restore
        if hibernation_complete_time > 0:
            time_since_hibernation = current_time - hibernation_complete_time
            if time_since_hibernation < 5:  # Wait at least 5 seconds after hibernation
                wait_time = 5 - time_since_hibernation
                print(f"Waiting {wait_time:.1f} more seconds after hibernation before restore attempt")
                return False
        
        # Check if we should wait before retry
        if last_restore_attempt > 0:
            time_since_last_attempt = current_time - last_restore_attempt
            min_retry_interval = min(30, 5 * (restore_retry_count + 1))  # Progressive backoff: 5s, 10s, 15s, 20s, 25s, 30s max
            
            if time_since_last_attempt < min_retry_interval:
                wait_time = min_retry_interval - time_since_last_attempt
                print(f"Waiting {wait_time:.1f} more seconds before retry attempt #{restore_retry_count + 1}")
                return False
        
        # Limit retry attempts
        if restore_retry_count >= 5:
            print(f"Maximum restore retry attempts ({restore_retry_count}) reached, giving up")
            store_action_log(
                action_type='restore_failed',
                user_id='system',
                details=f'Maximum retry attempts reached: {restore_retry_count}',
                status='error'
            )
            r.hmset('vm_state', {
                'restore_after_hibernation': 0,
                'restore_retry_count': 0,
                'status': 'HIBERNATED',
                'operation_start_time': 0
            })
            return False
        
        print(f"Attempting VM restore (attempt #{restore_retry_count + 1})...")
        store_action_log(
            action_type='restore_attempt',
            user_id='system',
            details=f'Attempt #{restore_retry_count + 1}'
        )
        
        # Update attempt tracking
        r.hmset('vm_state', {
            'restore_retry_count': restore_retry_count + 1,
            'last_restore_attempt': current_time,
            'status': 'RESTORING',
            'operation_start_time': current_time,
            'last_operation': current_time
        })
        
        # Make restore API call
        print("Calling Hyperstack API to restore VM...")
        restore_response = call_hyperstack_api('hibernate-restore')
        
        if restore_response and restore_response.get('status') is True:
            print("Restore API call successful - waiting for webhook confirmation")
            store_action_log(
                action_type='restore_initiated',
                user_id='system',
                details='Restore API call successful'
            )
            # Clear the restore flag only after successful API call
            r.hset('vm_state', 'restore_after_hibernation', 0)
            return True
        else:
            error_msg = restore_response.get('error', 'Unknown error') if restore_response else 'No response'
            print(f"Restore API call failed: {error_msg}")
            store_action_log(
                action_type='restore_failed',
                user_id='system',
                details=f'API call failed: {error_msg}',
                status='error'
            )
            
            # Check if error indicates VM is still hibernating
            if restore_response and isinstance(restore_response.get('error'), str):
                error_text = restore_response['error'].lower()
                if 'still going on' in error_text or 'hibernating' in error_text or 'shelving' in error_text:
                    print("VM is still hibernating, will retry later")
                    r.hset('vm_state', 'status', 'HIBERNATING')
                    return False
            
            # For other errors, revert to hibernated state but keep trying
            print("Restore failed, reverting to HIBERNATED state but will retry")
            r.hset('vm_state', 'status', 'HIBERNATED')
            return False
                
    except Exception as e:
        print(f"Error in attempt_restore_vm: {str(e)}")
        store_action_log(
            action_type='restore_error',
            user_id='system',
            details=f'Exception: {str(e)}',
            status='error'
        )
        r.hmset('vm_state', {
            'status': 'HIBERNATED',
            'operation_start_time': 0
        })
        return False

def auto_restore_after_hibernation():
    """Automatically restore VM if restore was requested during hibernation"""
    try:
        restore_flag = int(r.hget('vm_state', 'restore_after_hibernation') or 0)
        current_status = r.hget('vm_state', 'status')
        
        print(f"DEBUG: auto_restore_after_hibernation called, restore_flag: {restore_flag}, current_status: {current_status}")
        
        if restore_flag > 0 and current_status in ['HIBERNATED', 'HIBERNATING']:
            print("Auto-restoring VM after hibernation...")
            
            # If still hibernating, wait
            if current_status == 'HIBERNATING':
                print("VM still hibernating, will try again later")
                return
            
            # Attempt restore
            success = attempt_restore_vm()
            if not success:
                print("Auto-restore attempt failed, will retry later")
        else:
            print("DEBUG: No restore needed or VM not in correct state")
                
    except Exception as e:
        print(f"Error in auto_restore_after_hibernation: {str(e)}")

@app.route('/repair-state', methods=['POST'])
@require_auth
def repair_state():
    """Manually repair the VM state"""
    try:
        initialize_state()  # This will repair missing fields
        sync_redis_with_actual_state()  # Sync with actual VM state
        
        return jsonify({
            'success': True,
            'message': 'VM state repaired successfully',
            'current_state': r.hgetall('vm_state')
        })
        
    except Exception as e:
        return jsonify({'error': f'Repair failed: {str(e)}'}), 500
    
def monitor_vm_state():
    """Background thread to monitor VM state changes - simplified with webhook support"""
    while True:
        try:
            print("Checking VM state...")
            vm_data = r.hgetall('vm_state')
            current_status = vm_data.get('status', 'HIBERNATED')
            operation_start_time = float(vm_data.get('operation_start_time', 0))
            restore_flag = int(vm_data.get('restore_after_hibernation', 0))

            if not r.hexists('vm_state', 'status'):
                print("VM state missing status - repairing")
                initialize_state()  # This will now repair missing fields
            # Check for pending restore requests
            if restore_flag > 0:
                print("Found pending restore request, attempting restore")
                auto_restore_after_hibernation()
            
            # Handle stuck transitions
            if current_status in ['RESTORING', 'HIBERNATING']:
                # Check if operation has been running too long
                if operation_start_time > 0 and time.time() - operation_start_time > 600:  # 10 minutes
                    print(f"Operation {current_status} timed out after 10 minutes")
                    store_action_log(
                        action_type='operation_timeout',
                        user_id='system',
                        details=f'Operation {current_status} timed out after 10 minutes',
                        status='error'
                    )
                    
                    if current_status == 'RESTORING':
                        # Reset restore state but keep trying if flag is set
                        if restore_flag > 0:
                            print("Resetting stuck RESTORING state, will retry restore")
                            r.hmset('vm_state', {
                                'status': 'HIBERNATED',
                                'operation_start_time': 0,
                                'restore_retry_count': 0  # Reset retry count on timeout
                            })
                        else:
                            print("Resetting stuck RESTORING state to HIBERNATED")
                            r.hmset('vm_state', {
                                'status': 'HIBERNATED',
                                'operation_start_time': 0
                            })
                    elif current_status == 'HIBERNATING':
                        print("Forcing state sync after hibernation timeout")
                        sync_redis_with_actual_state()
            
            elif current_status in ['ACTIVE', 'HIBERNATED']:
                # Periodic sync for stable states only (less frequent)
                sync_redis_with_actual_state()
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Error in monitor_vm_state: {str(e)}")
            time.sleep(30)
def initialize_timer_state():
    """Initialize timer configuration in Redis"""
    if not r.exists('timer_config'):
        timer_config = {
            'hibernation_timeout': IDLE_TIMEOUT,  # Default from environment
            'timer_paused': 0,  # 0 = not paused, 1 = paused
            'pause_start_time': 0,
            'total_pause_time': 0,
            'last_timer_update': time.time()
        }
        r.hmset('timer_config', timer_config)
        print(f"Initialized timer config with {IDLE_TIMEOUT}s timeout")

def get_effective_idle_time():
    """Calculate effective idle time accounting for pauses"""
    try:
        vm_data = r.hgetall('vm_state')
        timer_config = r.hgetall('timer_config')
        
        user_activity_time = float(vm_data.get('user_activity_time', 0))
        timer_paused = int(timer_config.get('timer_paused', 0))
        pause_start_time = float(timer_config.get('pause_start_time', 0))
        total_pause_time = float(timer_config.get('total_pause_time', 0))
        
        if user_activity_time == 0:
            return 0
        
        current_time = time.time()
        raw_idle_time = current_time - user_activity_time
        
        # If currently paused, add ongoing pause time
        if timer_paused and pause_start_time > 0:
            ongoing_pause_time = current_time - pause_start_time
            effective_idle_time = raw_idle_time - total_pause_time - ongoing_pause_time
        else:
            effective_idle_time = raw_idle_time - total_pause_time
        
        return max(0, effective_idle_time)  # Never negative
        
    except Exception as e:
        print(f"Error calculating effective idle time: {str(e)}")
        return 0

def get_hibernation_timeout():
    """Get current hibernation timeout setting"""
    try:
        timer_config = r.hgetall('timer_config')
        return int(timer_config.get('hibernation_timeout', IDLE_TIMEOUT))
    except:
        return IDLE_TIMEOUT

@app.route('/timer-config', methods=['GET'])
@require_auth
def get_timer_config():
    """Get current timer configuration"""
    try:
        timer_config = r.hgetall('timer_config')
        vm_data = r.hgetall('vm_state')
        
        current_timeout = int(timer_config.get('hibernation_timeout', IDLE_TIMEOUT))
        timer_paused = int(timer_config.get('timer_paused', 0))
        effective_idle_time = get_effective_idle_time()
        
        return jsonify({
            'hibernation_timeout': current_timeout,
            'timer_paused': bool(timer_paused),
            'effective_idle_time': effective_idle_time,
            'time_until_hibernation': max(0, current_timeout - effective_idle_time),
            'pause_start_time': float(timer_config.get('pause_start_time', 0)),
            'total_pause_time': float(timer_config.get('total_pause_time', 0)),
            'vm_status': vm_data.get('status', 'HIBERNATED')
        })
        
    except Exception as e:
        print(f"Error getting timer config: {str(e)}")
        return jsonify({'error': 'Failed to get timer config'}), 500

@app.route('/timer-config', methods=['POST'])
@require_auth
def update_timer_config():
    """Update timer configuration"""
    try:
        data = request.get_json() or {}
        user_id = request.headers.get('X-User-ID', 'dashboard-admin')
        
        timer_config = r.hgetall('timer_config')
        updates = {}
        changes = []
        
        # Update hibernation timeout
        if 'hibernation_timeout' in data:
            new_timeout = int(data['hibernation_timeout'])
            if new_timeout < 60:  # Minimum 1 minute
                return jsonify({'error': 'Minimum timeout is 60 seconds'}), 400
            if new_timeout > 7200:  # Maximum 2 hours
                return jsonify({'error': 'Maximum timeout is 7200 seconds (2 hours)'}), 400
            
            old_timeout = int(timer_config.get('hibernation_timeout', IDLE_TIMEOUT))
            if new_timeout != old_timeout:
                updates['hibernation_timeout'] = new_timeout
                changes.append(f'timeout: {old_timeout}s → {new_timeout}s')
        
        if updates:
            r.hmset('timer_config', updates)
            
            # Log the changes
            store_action_log(
                action_type='timer_config_update',
                user_id=user_id,
                details=f'Updated timer config: {", ".join(changes)}'
            )
            
            return jsonify({
                'success': True,
                'message': f'Timer configuration updated: {", ".join(changes)}',
                'changes': changes
            })
        else:
            return jsonify({
                'success': True,
                'message': 'No changes made'
            })
            
    except Exception as e:
        print(f"Error updating timer config: {str(e)}")
        return jsonify({'error': 'Failed to update timer config'}), 500

@app.route('/pause-timer', methods=['POST'])
@require_auth
def pause_timer():
    """Pause the hibernation timer"""
    try:
        user_id = request.headers.get('X-User-ID', 'dashboard-admin')
        timer_config = r.hgetall('timer_config')
        vm_data = r.hgetall('vm_state')
        
        vm_status = vm_data.get('status', 'HIBERNATED')
        if vm_status != 'ACTIVE':
            return jsonify({
                'error': f'Cannot pause timer when VM is {vm_status}'
            }), 400
        
        timer_paused = int(timer_config.get('timer_paused', 0))
        if timer_paused:
            return jsonify({
                'error': 'Timer is already paused'
            }), 400
        
        current_time = time.time()
        r.hmset('timer_config', {
            'timer_paused': 1,
            'pause_start_time': current_time
        })
        
        store_action_log(
            action_type='timer_paused',
            user_id=user_id,
            details='Hibernation timer paused'
        )
        
        return jsonify({
            'success': True,
            'message': 'Hibernation timer paused'
        })
        
    except Exception as e:
        print(f"Error pausing timer: {str(e)}")
        return jsonify({'error': 'Failed to pause timer'}), 500

@app.route('/resume-timer', methods=['POST'])
@require_auth  
def resume_timer():
    """Resume the hibernation timer"""
    try:
        user_id = request.headers.get('X-User-ID', 'dashboard-admin')
        timer_config = r.hgetall('timer_config')
        
        timer_paused = int(timer_config.get('timer_paused', 0))
        if not timer_paused:
            return jsonify({
                'error': 'Timer is not paused'
            }), 400
        
        # Calculate pause duration and add to total
        pause_start_time = float(timer_config.get('pause_start_time', 0))
        total_pause_time = float(timer_config.get('total_pause_time', 0))
        
        if pause_start_time > 0:
            pause_duration = time.time() - pause_start_time
            total_pause_time += pause_duration
        
        r.hmset('timer_config', {
            'timer_paused': 0,
            'pause_start_time': 0,
            'total_pause_time': total_pause_time
        })
        
        store_action_log(
            action_type='timer_resumed',
            user_id=user_id,
            details=f'Hibernation timer resumed (was paused for {pause_duration:.1f}s)'
        )
        
        return jsonify({
            'success': True,
            'message': f'Hibernation timer resumed (was paused for {pause_duration:.1f}s)'
        })
        
    except Exception as e:
        print(f"Error resuming timer: {str(e)}")
        return jsonify({'error': 'Failed to resume timer'}), 500

@app.route('/reset-timer', methods=['POST'])
@require_auth
def reset_timer():
    """Reset the hibernation timer (restart countdown)"""
    try:
        user_id = request.headers.get('X-User-ID', 'dashboard-admin')
        vm_data = r.hgetall('vm_state')
        
        vm_status = vm_data.get('status', 'HIBERNATED')
        if vm_status != 'ACTIVE':
            return jsonify({
                'error': f'Cannot reset timer when VM is {vm_status}'
            }), 400
        
        current_time = time.time()
        
        # Reset user activity time and pause tracking
        r.hset('vm_state', 'user_activity_time', current_time)
        r.hmset('timer_config', {
            'timer_paused': 0,
            'pause_start_time': 0,
            'total_pause_time': 0
        })
        
        store_action_log(
            action_type='timer_reset',
            user_id=user_id,
            details='Hibernation timer reset'
        )
        
        return jsonify({
            'success': True,
            'message': 'Hibernation timer reset'
        })
        
    except Exception as e:
        print(f"Error resetting timer: {str(e)}")
        return jsonify({'error': 'Failed to reset timer'}), 500
        
def manage_hibernation():
    """Background thread to manage automatic hibernation with dynamic timer"""
    while True:
        try:
            print("Checking for idle VM to hibernate...")
            vm_data = r.hgetall('vm_state')
            timer_config = r.hgetall('timer_config')
            
            if not vm_data:
                time.sleep(60)
                continue
                
            current_status = vm_data.get('status', 'HIBERNATED')
            user_activity_time = float(vm_data.get('user_activity_time', 0))
            pending_requests = int(vm_data.get('pending_requests', 0))
            hibernation_requested = int(vm_data.get('hibernation_requested', 0))
            timer_paused = int(timer_config.get('timer_paused', 0))
            
            # Get dynamic timeout
            hibernation_timeout = get_hibernation_timeout()
            effective_idle_time = get_effective_idle_time()
            
            print(f"Hibernation check: status={current_status}, idle_time={effective_idle_time:.1f}s, timeout={hibernation_timeout}s, paused={bool(timer_paused)}")
            
            # Only hibernate if VM is active, idle beyond timeout, no pending requests, not manually requested to stay alive, and timer not paused
            if (current_status == 'ACTIVE' and 
                user_activity_time > 0 and
                effective_idle_time > hibernation_timeout and
                pending_requests == 0 and
                hibernation_requested == 0 and
                not timer_paused):
                
                print(f"Initiating hibernation due to inactivity ({effective_idle_time:.0f}s idle, timeout: {hibernation_timeout}s)")
                store_action_log(
                    action_type='auto_hibernation',
                    user_id='system',
                    details=f'Idle time: {effective_idle_time:.0f}s, timeout: {hibernation_timeout}s'
                )
                
                # Set state to HIBERNATING before making API call
                hibernation_start_time = time.time()
                r.hmset('vm_state', {
                    'status': 'HIBERNATING',
                    'last_operation': hibernation_start_time,
                    'operation_start_time': hibernation_start_time
                })
                
                # Reset pause tracking when hibernating
                r.hmset('timer_config', {
                    'timer_paused': 0,
                    'pause_start_time': 0,
                    'total_pause_time': 0
                })
                
                # Make hibernation API call
                print("Calling Hyperstack API to hibernate VM...")
                hibernate_response = call_hyperstack_api('hibernate')
                
                if hibernate_response and hibernate_response.get('status') is True:
                    print("Hibernation initiated successfully - waiting for webhook confirmation")
                else:
                    # If hibernation failed, revert to previous state
                    print("Failed to initiate hibernation, reverting state")
                    r.hset('vm_state', 'status', 'ACTIVE')
                    r.hset('vm_state', 'operation_start_time', 0)
                    
        except Exception as e:
            print(f"Error in manage_hibernation: {str(e)}")
            
        time.sleep(30)
# Webhook endpoint for Hyperstack notifications
@app.route('/webhook/hyperstack', methods=['POST'])
def hyperstack_webhook():
    """Handle webhook notifications from Hyperstack"""
    try:
        # Get the webhook payload
        payload = request.get_json()
        
        if not payload:
            print("Received empty webhook payload")
            return jsonify({'error': 'Empty payload'}), 400
        
        print(f"Received webhook payload: {json.dumps(payload, indent=2)}")
        
        # Store webhook log
        store_action_log(
            action_type='webhook_received',
            user_id='hyperstack',
            details=f'Payload: {json.dumps(payload)[:500]}'
        )
        
        # Increment webhook event counter
        r.hincrby('vm_state', 'webhook_events', 1)
        
        # Extract relevant information
        resource = payload.get('resource', {})
        operation = payload.get('operation', {})
        data = payload.get('data', {})
        
        # Verify this is for our VM
        vm_id = str(resource.get('id', ''))
        if vm_id != VM_ID:
            print(f"Webhook for different VM ID: {vm_id}, ignoring")
            return jsonify({'message': 'Different VM'}), 200
        
        # Get operation details
        operation_name = operation.get('name', '')
        operation_status = operation.get('status', '')
        vm_status = data.get('status', '')
        power_state = data.get('power_state', '')
        vm_state = data.get('vm_state', '')

        print(f"Received webhook - operation: {operation_name}, status: {operation_status}")
        print(f"VM {vm_id}: operation={operation_name}, op_status={operation_status}, vm_status={vm_status}, power={power_state}, state={vm_state}")
        
        current_time = time.time()
        
        # Handle hibernation operations
        if operation_name == 'shelveInstances':
            if operation_status == 'HIBERNATING' or vm_status == 'HIBERNATING':
                print("Hibernation in progress - maintaining HIBERNATING state")
                r.hmset('vm_state', {
                    'status': 'HIBERNATING',
                    'last_operation': current_time
                })
                store_action_log(
                    action_type='hibernation_progress',
                    user_id='hyperstack',
                    details=f'Operation: {operation_name}, Status: {operation_status}'
                )
            
            elif (operation_status == 'COMPLETED' or 
                  vm_status == 'HIBERNATED' or 
                  power_state == 'HIBERNATED' or
                  vm_state == 'hibernated'):
                print("Hibernation completed - updating state to HIBERNATED")
                r.hmset('vm_state', {
                    'status': 'HIBERNATED',
                    'last_operation': current_time,
                    'operation_start_time': 0,
                    'hibernation_requested': 0,
                    'user_activity_time': 0,
                    'hibernation_complete_time': current_time,  # Mark when hibernation completed
                    'restore_retry_count': 0  # Reset retry count on successful hibernation
                })
                store_action_log(
                    action_type='hibernation_completed',
                    user_id='hyperstack',
                    details='VM successfully hibernated'
                )
                
                # Check if we need to auto-restore after hibernation
                auto_restore_after_hibernation()
        
        # Handle restore operations
        elif operation_name == 'unshelveInstances':
            if operation_status == 'RESTORING' or vm_status == 'RESTORING':
                print("Restore in progress - maintaining RESTORING state")
                r.hmset('vm_state', {
                    'status': 'RESTORING',
                    'last_operation': current_time
                })
                store_action_log(
                    action_type='restore_progress',
                    user_id='hyperstack',
                    details=f'Operation: {operation_name}, Status: {operation_status}'
                )
            
            elif (operation_status == 'COMPLETED' or 
                  vm_status == 'ACTIVE' or 
                  power_state == 'RUNNING' or
                  vm_state == 'active'):
                print("Restore completed - updating state to ACTIVE")
                r.hmset('vm_state', {
                    'status': 'ACTIVE',
                    'last_operation': current_time,
                    'user_activity_time': current_time,
                    'operation_start_time': 0,
                    'pending_requests': 0,
                    'restore_retry_count': 0,  # Reset retry count on successful restore
                    'restore_after_hibernation': 0  # Clear any pending restore flag
                })
                store_action_log(
                    action_type='restore_completed',
                    user_id='hyperstack',
                    details='VM successfully restored to active state'
                )
        
        # Handle general status updates
        else:
            if vm_status == 'ACTIVE' and power_state == 'RUNNING':
                current_redis_state = r.hget('vm_state', 'status')
                if current_redis_state != 'ACTIVE':
                    print("VM became active - updating state")
                    current_user_activity = float(r.hget('vm_state', 'user_activity_time') or 0)
                    
                    updates = {
                        'status': 'ACTIVE',
                        'last_operation': current_time,
                        'operation_start_time': 0,
                        'restore_retry_count': 0,
                        'restore_after_hibernation': 0
                    }
                    
                    if current_user_activity == 0:
                        updates['user_activity_time'] = current_time
                        print("Setting initial user activity time")
                    
                    r.hmset('vm_state', updates)
                    store_action_log(
                        action_type='vm_became_active',
                        user_id='hyperstack',
                        details='VM transitioned to active state'
                    )
            
            elif vm_status == 'HIBERNATED' or power_state == 'HIBERNATED':
                current_redis_state = r.hget('vm_state', 'status')
                if current_redis_state != 'HIBERNATED':
                    print("VM became hibernated - updating state")
                    r.hmset('vm_state', {
                        'status': 'HIBERNATED',
                        'last_operation': current_time,
                        'operation_start_time': 0,
                        'hibernation_requested': 0,
                        'user_activity_time': 0,
                        'hibernation_complete_time': current_time,
                        'restore_retry_count': 0
                    })
                    store_action_log(
                        action_type='vm_became_hibernated',
                        user_id='hyperstack',
                        details='VM transitioned to hibernated state'
                    )
                    
                    # Check if we need to auto-restore after hibernation
                    auto_restore_after_hibernation()
        
        return jsonify({'message': 'Webhook processed successfully'}), 200
        
    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        store_action_log(
            action_type='webhook_error',
            user_id='hyperstack',
            details=f'Error processing webhook: {str(e)}',
            status='error'
        )
        return jsonify({'error': 'Webhook processing failed'}), 500

# Initialize state and start background threads
initialize_state()
initialize_timer_state()
threading.Thread(target=monitor_vm_state, daemon=True).start()
threading.Thread(target=manage_hibernation, daemon=True).start()

@app.route('/user-search')
@require_auth
def user_search():
    """User search and analytics page"""
    return render_template('user-search.html')

@app.route('/status', methods=['GET'])
def get_status():
    """Get current VM status with timer information"""
    try:
        state = r.hgetall('vm_state')
        timer_config = r.hgetall('timer_config')
        
        user_activity_time = float(state.get('user_activity_time', 0))
        current_time = time.time()
        
        # Get dynamic values
        hibernation_timeout = get_hibernation_timeout()
        effective_idle_time = get_effective_idle_time()
        timer_paused = int(timer_config.get('timer_paused', 0))
        
        response_data = {
            'status': state.get('status', 'HIBERNATED'),
            'last_activity': float(state.get('last_activity', 0)),
            'user_activity_time': user_activity_time,
            'idle_seconds': effective_idle_time,
            'raw_idle_seconds': current_time - user_activity_time if user_activity_time > 0 else 0,
            'pending_requests': int(state.get('pending_requests', 0)),
            'last_operation': float(state.get('last_operation', 0)),
            'last_health_check': float(state.get('last_health_check', 0)),
            'operation_start_time': float(state.get('operation_start_time', 0)),
            'webhook_events': int(state.get('webhook_events', 0)),
            'restore_after_hibernation': int(state.get('restore_after_hibernation', 0)),
            'hibernation_requested': int(state.get('hibernation_requested', 0)),
            'restore_retry_count': int(state.get('restore_retry_count', 0)),
            'last_restore_attempt': float(state.get('last_restore_attempt', 0)),
            'hibernation_complete_time': float(state.get('hibernation_complete_time', 0)),
            'gpu_service_healthy': check_gpu_service_health() if state.get('status') == 'ACTIVE' else False,
            'hibernation_timer': max(0, hibernation_timeout - effective_idle_time) if user_activity_time > 0 else 0,
            'hibernation_timeout': hibernation_timeout,
            'timer_paused': bool(timer_paused),
            'total_pause_time': float(timer_config.get('total_pause_time', 0))
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error getting status: {str(e)}")
        return jsonify({'error': 'Failed to get status'}), 500

@app.route('/activate', methods=['POST'])
def activate_vm():
    """Activate the VM (restore from hibernation)"""
    try:
        current_status = r.hget('vm_state', 'status')

        if current_status is None:
            print("VM state is None - attempting recovery")
            current_status = recover_vm_state()

        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        tool = request.headers.get('X-Tool')
        processing_id = request.headers.get('X-Processing-ID')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'activate', tool, processing_id, email)
        
        # Increment pending requests
        r.hincrby('vm_state', 'pending_requests', 1)
        
        print(f"Activation request received from user {user_id}, current status: {current_status}")
        
        # If already active and healthy, just update user activity
        if current_status == 'ACTIVE':
            if check_gpu_service_health():
                r.hset('vm_state', 'user_activity_time', time.time())
                r.hset('vm_state', 'hibernation_requested', 0)
                r.hincrby('vm_state', 'pending_requests', -1)
                store_action_log(
                    action_type='activate_already_active',
                    user_id=user_id or 'unknown',
                    details=f'VM already active, Email: {email or "N/A"}'
                )
                return jsonify({
                    'status': 'ACTIVE', 
                    'message': 'VM is already active and healthy'
                })
        
        # If already restoring, return current state
        if current_status == 'RESTORING':
            return jsonify({
                'status': current_status,
                'message': f'VM is currently restoring, please wait'
            })
        
        # If currently hibernating, set flag to restore after hibernation completes
        if current_status == 'HIBERNATING':
            print("VM is hibernating, setting flag to restore after hibernation completes")
            r.hmset('vm_state', {
                'restore_after_hibernation': 1,
                'restore_retry_count': 0  # Reset retry count for new request
            })
            store_action_log(
                action_type='activate_during_hibernation',
                user_id=user_id or 'unknown',
                details=f'Set restore flag during hibernation, Email: {email or "N/A"}'
            )
            return jsonify({
                'status': 'HIBERNATING',
                'message': 'VM is hibernating. Will automatically restore once hibernation completes.',
                'will_auto_restore': True
            })
        
        # If hibernated, attempt restore
        if current_status == 'HIBERNATED':
            print("VM is hibernated, attempting immediate restore")
            r.hmset('vm_state', {
                'restore_after_hibernation': 1,
                'restore_retry_count': 0
            })
            
            store_action_log(
                action_type='activate_from_hibernated',
                user_id=user_id or 'unknown',
                details=f'Attempting restore from hibernated state, Email: {email or "N/A"}'
            )
            
            # Try restore immediately
            success = attempt_restore_vm()
            
            if success:
                return jsonify({
                    'status': 'RESTORING',
                    'message': 'VM restore initiated successfully'
                })
            else:
                # Keep the flag set so monitor will retry
                return jsonify({
                    'status': 'HIBERNATED',
                    'message': 'VM restore attempt failed, will retry automatically',
                    'will_auto_restore': True
                })
        
        # Invalid state for activation
        r.hincrby('vm_state', 'pending_requests', -1)
        return jsonify({
            'error': f'Cannot activate VM from current state: {current_status}'
        }), 400
        
    except Exception as e:
        r.hincrby('vm_state', 'pending_requests', -1)
        print(f"Activation error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/wait-for-active', methods=['POST'])
def wait_for_active():
    """Wait for VM to become active with timeout"""
    try:
        data = request.get_json() or {}
        timeout = data.get('timeout', 300)  # 5 minutes default
        start_time = time.time()
        
        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        processing_id = request.headers.get('X-Processing-ID')
        tool = request.headers.get('X-Tool')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'wait-for-active', tool, processing_id, email)
        
        while time.time() - start_time < timeout:
            current_status = r.hget('vm_state', 'status')
            
            if current_status == 'ACTIVE':
                if check_gpu_service_health():
                    r.hset('vm_state', 'user_activity_time', time.time())
                    store_action_log(
                        action_type='wait_for_active_success',
                        user_id=user_id or 'unknown',
                        details=f'VM became active after {time.time() - start_time:.1f}s, Email: {email or "N/A"}'
                    )
                    return jsonify({
                        'status': 'ACTIVE',
                        'message': 'VM is now active and healthy',
                        'wait_time': time.time() - start_time
                    })
            
            # If VM went back to hibernated, it's an error
            if current_status == 'HIBERNATED':
                # Check if it's still trying to restore
                restore_flag = int(r.hget('vm_state', 'restore_after_hibernation') or 0)
                if restore_flag == 0:
                    store_action_log(
                        action_type='wait_for_active_failed',
                        user_id=user_id or 'unknown',
                        details=f'VM failed to activate, Email: {email or "N/A"}',
                        status='error'
                    )
                    return jsonify({
                        'error': 'VM failed to activate',
                        'current_status': current_status
                    }), 400
            
            time.sleep(5)  # Check every 5 seconds
        
        # Timeout reached
        current_status = r.hget('vm_state', 'status')
        store_action_log(
            action_type='wait_for_active_timeout',
            user_id=user_id or 'unknown',
            details=f'Timeout after {timeout}s, Status: {current_status}, Email: {email or "N/A"}',
            status='error'
        )
        return jsonify({
            'error': 'Timeout waiting for VM to become active',
            'current_status': current_status,
            'timeout': timeout
        }), 408
        
    except Exception as e:
        print(f"Wait for active error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/activity', methods=['POST'])
def update_activity():
    """Update user activity time"""
    try:
        current_status = r.hget('vm_state', 'status')
        
        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        processing_id = request.headers.get('X-Processing-ID')
        tool = request.headers.get('X-Tool')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'activity', tool, processing_id, email)
        
        if current_status == 'ACTIVE':
            r.hset('vm_state', 'user_activity_time', time.time())
            r.hset('vm_state', 'hibernation_requested', 0)
            
            return jsonify({
                'success': True,
                'message': 'User activity time updated',
                'status': current_status
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Cannot update activity - VM is {current_status}',
                'status': current_status
            })
        
    except Exception as e:
        print(f"Activity update error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/release', methods=['POST'])
def release_request():
    """Release a request and update activity time"""
    try:
        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        processing_id = request.headers.get('X-Processing-ID')
        tool = request.headers.get('X-Tool')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'release', tool, processing_id, email)
        
        r.hset('vm_state', 'user_activity_time', time.time())
        
        # Decrement pending requests (don't go below 0)
        current_pending = int(r.hget('vm_state', 'pending_requests') or 0)
        if current_pending > 0:
            r.hincrby('vm_state', 'pending_requests', -1)
            new_pending = current_pending - 1
        else:
            new_pending = 0
        
        return jsonify({
            'success': True,
            'message': 'Request released',
            'remaining_pending': new_pending
        })
        
    except Exception as e:
        print(f"Release error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/keep-alive', methods=['POST'])
def keep_alive():
    """Prevent hibernation by setting hibernation_requested flag"""
    try:
        data = request.get_json() or {}
        duration = data.get('duration', 300)  # Default 5 minutes
        
        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        processing_id = request.headers.get('X-Processing-ID')
        tool = request.headers.get('X-Tool')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'keep-alive', tool, processing_id, email)
        
        current_status = r.hget('vm_state', 'status')
        
        if current_status == 'ACTIVE':
            # Set hibernation_requested flag to prevent automatic hibernation
            r.hset('vm_state', 'hibernation_requested', 1)
            r.hset('vm_state', 'user_activity_time', time.time())
            
            store_action_log(
                action_type='keep_alive',
                user_id=user_id or 'unknown',
                details=f'Keep alive for {duration}s, Email: {email or "N/A"}'
            )
            
            # Optionally set a timer to clear the flag after duration
            def clear_hibernation_flag():
                time.sleep(duration)
                r.hset('vm_state', 'hibernation_requested', 0)
                store_action_log(
                    action_type='keep_alive_expired',
                    user_id='system',
                    details=f'Keep alive expired after {duration}s for user {user_id}'
                )
                print(f"Cleared hibernation prevention flag after {duration} seconds")
            
            threading.Thread(target=clear_hibernation_flag, daemon=True).start()
            
            return jsonify({
                'success': True,
                'message': f'VM will be kept alive for {duration} seconds',
                'duration': duration
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Cannot keep alive - VM is {current_status}',
                'status': current_status
            })
        
    except Exception as e:
        print(f"Keep alive error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/force-sync', methods=['POST'])
def force_sync():
    """Force synchronization with actual VM status"""
    try:
        # Get user ID for logging
        user_id = request.headers.get('X-User-ID', 'unknown')
        
        sync_redis_with_actual_state()
        current_status = r.hget('vm_state', 'status')
        
        store_action_log(
            action_type='force_sync',
            user_id=user_id,
            details=f'Force sync requested, result status: {current_status}'
        )
        
        return jsonify({
            'success': True,
            'message': 'State synchronized',
            'current_status': current_status
        })
        
    except Exception as e:
        print(f"Force sync error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/hibernate', methods=['POST'])
def force_hibernate():
    """Force hibernation of the VM"""
    try:
        current_status = r.hget('vm_state', 'status')
        
        # Get user ID and email from headers
        user_id = request.headers.get('X-User-ID')
        processing_id = request.headers.get('X-Processing-ID')
        tool = request.headers.get('X-Tool')
        email = request.headers.get('X-Email')
        
        # Track user request
        if user_id:
            track_user_request(user_id, 'hibernate', tool, processing_id, email)
        
        if current_status != 'ACTIVE':
            return jsonify({
                'error': f'Cannot hibernate VM from current state: {current_status}'
            }), 400
        
        # Set state to hibernating
        hibernation_start_time = time.time()
        r.hmset('vm_state', {
            'status': 'HIBERNATING',
            'last_operation': hibernation_start_time,
            'operation_start_time': hibernation_start_time,
            'hibernation_requested': 1  # Mark as manually requested
        })
        
        store_action_log(
            action_type='force_hibernation',
            user_id=user_id or 'unknown',
            details=f'Manual hibernation requested, Email: {email or "N/A"}'
        )
        
        # Make hibernation API call
        print("Calling Hyperstack API to hibernate VM...")
        hibernate_response = call_hyperstack_api('hibernate')
        
        if hibernate_response and hibernate_response.get('status') is True:
            return jsonify({
                'status': 'HIBERNATING',
                'message': 'VM hibernation initiated successfully - waiting for webhook confirmation'
            })
        else:
            # Revert state on failure
            r.hset('vm_state', 'status', 'ACTIVE')
            r.hset('vm_state', 'operation_start_time', 0)
            r.hset('vm_state', 'hibernation_requested', 0)
            store_action_log(
                action_type='hibernation_failed',
                user_id=user_id or 'unknown',
                details=f'Hibernation API call failed: {hibernate_response}',
                status='error'
            )
            return jsonify({
                'error': 'Failed to initiate hibernation',
                'details': hibernate_response
            }), 500
            
    except Exception as e:
        print(f"Force hibernate error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/clear-restore-flag', methods=['POST'])
def clear_restore_flag():
    """Clear the restore_after_hibernation flag (emergency endpoint)"""
    try:
        user_id = request.headers.get('X-User-ID', 'unknown')
        
        r.hmset('vm_state', {
            'restore_after_hibernation': 0,
            'restore_retry_count': 0
        })
        
        store_action_log(
            action_type='clear_restore_flag',
            user_id=user_id,
            details='Restore flag manually cleared'
        )
        
        return jsonify({
            'success': True,
            'message': 'Restore flag cleared'
        })
        
    except Exception as e:
        print(f"Clear restore flag error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/debug', methods=['GET'])
def debug_state():
    """Get detailed debug information"""
    try:
        state = r.hgetall('vm_state')
        current_time = time.time()
        
        # Add computed fields for debugging
        debug_info = dict(state)
        debug_info['current_time'] = current_time
        
        user_activity_time = float(state.get('user_activity_time', 0))
        last_restore_attempt = float(state.get('last_restore_attempt', 0))
        hibernation_complete_time = float(state.get('hibernation_complete_time', 0))
        operation_start_time = float(state.get('operation_start_time', 0))
        
        debug_info['time_since_user_activity'] = current_time - user_activity_time if user_activity_time > 0 else 0
        debug_info['time_since_last_restore_attempt'] = current_time - last_restore_attempt if last_restore_attempt > 0 else 0
        debug_info['time_since_hibernation_complete'] = current_time - hibernation_complete_time if hibernation_complete_time > 0 else 0
        debug_info['time_since_operation_start'] = current_time - operation_start_time if operation_start_time > 0 else 0
        
        # Check if restore should be attempted
        restore_retry_count = int(state.get('restore_retry_count', 0))
        min_retry_interval = min(30, 5 * (restore_retry_count + 1))
        
        debug_info['next_retry_allowed_in'] = max(0, min_retry_interval - debug_info['time_since_last_restore_attempt']) if last_restore_attempt > 0 else 0
        debug_info['hibernation_wait_remaining'] = max(0, 5 - debug_info['time_since_hibernation_complete']) if hibernation_complete_time > 0 else 0
        
        return jsonify(debug_info)
        
    except Exception as e:
        print(f"Debug error: {str(e)}")
        return jsonify({'error': 'Failed to get debug info'}), 500

@app.route('/users', methods=['GET'])
def get_users():
    """Get user statistics and activity with optional email search"""
    try:
        search_email = request.args.get('email', '')
        limit = int(request.args.get('limit', 50))
        
        user_stats = get_user_stats(search_email=search_email, limit=limit)
        return jsonify(user_stats)
        
    except Exception as e:
        print(f"Error getting user stats: {str(e)}")
        return jsonify({'error': 'Failed to get user stats'}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get action logs with optional filtering"""
    try:
        limit = int(request.args.get('limit', 100))
        days_back = int(request.args.get('days_back', 7))
        
        logs = get_action_logs(limit=limit, days_back=days_back)
        return jsonify({
            'logs': logs,
            'total_returned': len(logs)
        })
        
    except Exception as e:
        print(f"Error getting logs: {str(e)}")
        return jsonify({'error': 'Failed to get logs'}), 500

@app.route('/dashboard')
@require_auth
def dashboard():
    """Responsive web dashboard (requires authentication)"""
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)