"""
Redis utilities for performance enhancement across the application.

Provides optimized Redis operations for caching, queuing, and rate limiting.
"""

import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List
from functools import wraps

import redis.asyncio as redis
from redis.asyncio import Redis

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

# Global Redis client
redis_client: Optional[Redis] = None


async def get_redis() -> Redis:
    """Get Redis client instance (singleton pattern)."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,  # Keep binary for pickle
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
    return redis_client


class RedisCache:
    """High-performance caching wrapper with intelligent serialization."""

    def __init__(self, key_prefix: str = "", default_ttl: int = 3600):
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl

    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self.key_prefix}:{key}" if self.key_prefix else key

    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with automatic deserialization."""
        try:
            client = await get_redis()
            full_key = self._make_key(key)
            data = await client.get(full_key)

            if data is None:
                return default

            # Try JSON first, fallback to pickle
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return pickle.loads(data)

        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize_json: bool = True
    ) -> bool:
        """Set value in cache with intelligent serialization."""
        try:
            client = await get_redis()
            full_key = self._make_key(key)

            # Serialize based on data type and preference
            if serialize_json and self._is_json_serializable(value):
                data = json.dumps(value, default=str)
            else:
                data = pickle.dumps(value)

            expire_time = ttl or self.default_ttl
            await client.setex(full_key, expire_time, data)
            return True

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            client = await get_redis()
            full_key = self._make_key(key)
            result = await client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        try:
            client = await get_redis()
            full_pattern = self._make_key(pattern)
            keys = await client.keys(full_pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            client = await get_redis()
            full_key = self._make_key(key)
            return await client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter value."""
        try:
            client = await get_redis()
            full_key = self._make_key(key)

            # Use atomic increment with optional expiration
            pipe = client.pipeline()
            pipe.incrby(full_key, amount)
            if ttl:
                pipe.expire(full_key, ttl)
            result = await pipe.execute()
            return result[0]
        except Exception as e:
            logger.error(f"Cache increment error for {key}: {e}")
            return 0

    @staticmethod
    def _is_json_serializable(value: Any) -> bool:
        """Check if value can be JSON serialized."""
        try:
            json.dumps(value, default=str)
            return True
        except (TypeError, ValueError):
            return False


class RedisQueue:
    """High-performance message queue for background processing."""

    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.processing_suffix = ":processing"

    async def enqueue(self, data: Any, priority: int = 0) -> bool:
        """Add item to queue with optional priority."""
        try:
            client = await get_redis()

            # Use Redis list with score for priority (0 = high priority)
            item = {
                "data": data,
                "enqueued_at": datetime.utcnow().isoformat(),
                "priority": priority,
                "attempts": 0
            }

            # Add to sorted set with timestamp + priority for ordering
            score = (priority * -1000000) + datetime.utcnow().timestamp()
            await client.zadd(
                self.queue_name,
                {json.dumps(item, default=str): score}
            )
            return True

        except Exception as e:
            logger.error(f"Queue enqueue error for {self.queue_name}: {e}")
            return False

    async def dequeue(self, timeout: int = 10) -> Optional[Dict]:
        """Get next item from queue (highest priority first)."""
        try:
            client = await get_redis()

            # Get highest priority item (lowest score)
            result = await client.zpopmin(self.queue_name, count=1)

            if not result:
                return None

            item_json, score = result[0]
            item = json.loads(item_json)

            # Move to processing queue for monitoring
            await client.zadd(
                f"{self.queue_name}{self.processing_suffix}",
                {item_json: datetime.utcnow().timestamp()}
            )

            return item

        except Exception as e:
            logger.error(f"Queue dequeue error for {self.queue_name}: {e}")
            return None

    async def complete(self, item_id: str) -> bool:
        """Mark item as completed and remove from processing queue."""
        try:
            client = await get_redis()
            await client.zrem(f"{self.queue_name}{self.processing_suffix}", item_id)
            return True
        except Exception as e:
            logger.error(f"Queue complete error for {self.queue_name}: {e}")
            return False

    async def requeue_stale(self, max_processing_time: int = 300) -> int:
        """Requeue items that have been processing too long."""
        try:
            client = await get_redis()
            processing_queue = f"{self.queue_name}{self.processing_suffix}"

            # Find stale items
            cutoff_time = datetime.utcnow().timestamp() - max_processing_time
            stale_items = await client.zrangebyscore(
                processing_queue, 0, cutoff_time, withscores=True
            )

            if not stale_items:
                return 0

            # Move stale items back to main queue with higher priority
            pipe = client.pipeline()
            requeued_count = 0

            for item_json, processing_time in stale_items:
                item = json.loads(item_json)
                item["attempts"] += 1

                # Only requeue if attempts < 3
                if item["attempts"] < 3:
                    score = ((item["priority"] + 10) * -1000000) + datetime.utcnow().timestamp()
                    pipe.zadd(self.queue_name, {item_json: score})
                    pipe.zrem(processing_queue, item_json)
                    requeued_count += 1
                else:
                    # Remove items with too many attempts
                    pipe.zrem(processing_queue, item_json)

            await pipe.execute()
            return requeued_count

        except Exception as e:
            logger.error(f"Queue requeue stale error for {self.queue_name}: {e}")
            return 0


class RedisRateLimiter:
    """Sliding window rate limiter using Redis."""

    def __init__(self, key_prefix: str = "rate_limit"):
        self.key_prefix = key_prefix

    async def is_allowed(
        self,
        identifier: str,
        limit: int,
        window: int,
        increment: int = 1
    ) -> Dict[str, Union[bool, int, float]]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            limit: Max requests allowed
            window: Time window in seconds
            increment: Amount to increment (default: 1)

        Returns:
            Dict with: allowed (bool), remaining (int), reset_time (float)
        """
        try:
            client = await get_redis()
            key = f"{self.key_prefix}:{identifier}"
            current_time = datetime.utcnow().timestamp()

            # Use Redis sorted set for sliding window
            pipe = client.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, current_time - window)

            # Count current entries
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration
            pipe.expire(key, window)

            results = await pipe.execute()
            _, current_count, _, _ = results

            # Check if allowed
            allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            reset_time = current_time + window

            return {
                "allowed": allowed,
                "remaining": remaining,
                "reset_time": reset_time,
                "current_count": current_count
            }

        except Exception as e:
            logger.error(f"Rate limiter error for {identifier}: {e}")
            # Fail open - allow request if Redis is down
            return {
                "allowed": True,
                "remaining": limit,
                "reset_time": datetime.utcnow().timestamp() + window,
                "current_count": 0
            }


# Pre-configured cache instances
user_cache = RedisCache("user", default_ttl=1800)  # 30 minutes
api_cache = RedisCache("api", default_ttl=300)    # 5 minutes
template_cache = RedisCache("template", default_ttl=3600)  # 1 hour
session_cache = RedisCache("session", default_ttl=86400)  # 24 hours

# Pre-configured queue instances
email_queue = RedisQueue("email")
background_queue = RedisQueue("background")

# Pre-configured rate limiter
auth_rate_limiter = RedisRateLimiter("auth")
api_rate_limiter = RedisRateLimiter("api")


def cache_result(ttl: int = 300, cache_instance: Optional[RedisCache] = None):
    """
    Decorator for caching function results.

    Args:
        ttl: Cache time-to-live in seconds
        cache_instance: Custom cache instance (defaults to api_cache)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Use provided cache instance or default
            cache = cache_instance or api_cache

            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set for {func.__name__}")

            return result
        return wrapper
    return decorator


async def close_redis():
    """Close Redis connection (for cleanup)."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None