from loguru import logger
import redis
from app.core.config import settings

# Create a thread-safe connection pool using the REDIS_URL from .env
pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client instance backed by the connection pool.
    """
    return redis.Redis(connection_pool=pool)

def ping_redis() -> bool:
    """
    Checks if the Redis server is reachable.
    """
    try:
        client = get_redis_client()
        return client.ping()
    except Exception as e:
        logger.warning(f"Redis ping failed: {e}")
        return False
