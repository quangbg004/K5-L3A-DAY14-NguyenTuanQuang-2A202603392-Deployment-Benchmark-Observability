from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from .config import settings
from .redis_client import r


WINDOW_MS = 60_000

# Every worker uses the Redis clock and updates the window in one operation.
_admit_request = r.register_script("""
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local now = redis.call('TIME')
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)

redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_ms = tonumber(oldest[2]) or now_ms
    return math.max(1, math.ceil((oldest_ms + window_ms - now_ms) / 1000))
end

redis.call('ZADD', key, now_ms, ARGV[3])
redis.call('PEXPIRE', key, window_ms)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_hash = sha256(key.encode()).hexdigest()
    retry_after = _admit_request(
        keys=[f"agent:rate:{key_hash}"],
        args=[settings.rate_limit_per_minute, WINDOW_MS, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
