import time
import requests
from django.conf import settings
from django.core.cache import cache
from redis import Redis
from threading import Lock

# Redis connection for refcount
redis = Redis.from_url(settings.REDIS_URL)
_start_lock = Lock()
REFCOUNT_KEY = "gpu_active_count"
LAST_USED_KEY = "gpu_last_used"

class GPUOrchestrator:
    @classmethod
    def _state(cls):
        resp = requests.get(
            f"{settings.HYPERSTACK_BASE}/core/virtual-machines/{settings.HYPERSTACK_VM_ID}",
            auth=(settings.HYPERSTACK_USER, settings.HYPERSTACK_PASS),
        )
        return resp.json().get('state')

    @classmethod
    def _start_vm(cls):
        requests.get(
            f"{settings.HYPERSTACK_BASE}/core/virtual-machines/{settings.HYPERSTACK_VM_ID}/start",
            auth=(settings.HYPERSTACK_USER, settings.HYPERSTACK_PASS),
        )

    @classmethod
    def acquire(cls, timeout=300, poll_interval=5):
        # Thread-safe VM start
        with _start_lock:
            if cls._state() != 'running':
                cls._start_vm()
                waited = 0
                while waited < timeout:
                    if cls._state() == 'running':
                        break
                    time.sleep(poll_interval)
                    waited += poll_interval
                else:
                    raise TimeoutError("GPU-VM did not start in time")
        # Increment active job count
        redis.incr(REFCOUNT_KEY)
        # Stamp last-used
        cache.set(LAST_USED_KEY, time.time())
        return True

    @classmethod
    def release(cls):
        remaining = redis.decr(REFCOUNT_KEY)
        cache.set(LAST_USED_KEY, time.time())
        return remaining

    @classmethod
    def auto_hibernate(cls):
        last = cache.get(LAST_USED_KEY) or 0
        active = int(redis.get(REFCOUNT_KEY) or 0)
        if active <= 0 and (time.time() - last) > 15 * 60 and cls._state() == 'running':
            requests.get(
                f"{settings.HYPERSTACK_BASE}/core/virtual-machines/{settings.HYPERSTACK_VM_ID}/hibernate",
                auth=(settings.HYPERSTACK_USER, settings.HYPERSTACK_PASS),
            )