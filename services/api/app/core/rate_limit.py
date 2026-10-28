"""Rate limit cửa sổ cố định. Dùng Redis nếu có, fallback bộ nhớ trong tiến trình."""
import threading
import time

from app.core.config import get_settings

_lock = threading.Lock()
_memory: dict[str, tuple[int, float]] = {}
_redis = None
_redis_checked = False


def _get_redis():
    global _redis, _redis_checked
    if not _redis_checked:
        _redis_checked = True
        try:
            import redis

            r = redis.Redis.from_url(get_settings().redis_url, socket_timeout=0.3, socket_connect_timeout=0.3)
            r.ping()
            _redis = r
        except Exception:
            _redis = None
    return _redis


def reset_memory() -> None:
    with _lock:
        _memory.clear()


def hit(key: str, limit: int, window_sec: int = 60) -> tuple[bool, int]:
    """Trả về (được phép, số lần đã dùng)."""
    if get_settings().environment == "test" and not key.startswith("test:"):
        r = None
    else:
        r = _get_redis()
    bucket = f"rl:{key}:{int(time.time() // window_sec)}"
    if r is not None:
        try:
            n = r.incr(bucket)
            if n == 1:
                r.expire(bucket, window_sec)
            return n <= limit, int(n)
        except Exception:
            pass
    with _lock:
        count, exp = _memory.get(bucket, (0, time.time() + window_sec))
        count += 1
        _memory[bucket] = (count, exp)
        now = time.time()
        for k in [k for k, (_, e) in _memory.items() if e < now]:
            _memory.pop(k, None)
        return count <= limit, count
