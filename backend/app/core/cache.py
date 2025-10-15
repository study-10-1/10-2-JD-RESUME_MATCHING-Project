"""
Redis Cache Utilities
"""
import redis
from typing import Optional, Any
import pickle
from functools import wraps

from app.core.config import settings


# Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)


def get_cache(key: str) -> Optional[Any]:
    """Get value from cache"""
    try:
        cached = redis_client.get(key)
        if cached:
            return pickle.loads(cached)
        return None
    except Exception as e:
        print(f"Cache get error: {e}")
        return None


def set_cache(key: str, value: Any, expire: int = 3600) -> bool:
    """Set value in cache"""
    try:
        redis_client.setex(key, expire, pickle.dumps(value))
        return True
    except Exception as e:
        print(f"Cache set error: {e}")
        return False


def delete_cache(key: str) -> bool:
    """Delete value from cache"""
    try:
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Cache delete error: {e}")
        return False


def cache_result(expire: int = 3600):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Check cache
            cached = get_cache(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            set_cache(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

