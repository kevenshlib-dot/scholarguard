"""
Token-bucket rate limiter backed by Redis.

Provides a configurable ``rate_limit`` dependency factory so each route (or
role) can have its own throughput cap.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.config import Settings, get_settings

# ── Redis connection singleton ──────────────────────────────────────────

_redis_pool: Optional[Redis] = None


async def get_redis(settings: Settings = Depends(get_settings)) -> Redis:
    """Return (and lazily create) a shared async Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool (called at shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Token-bucket implementation ─────────────────────────────────────────

# Lua script for atomic token-bucket check-and-consume.
# KEYS[1] = bucket key
# ARGV[1] = max_tokens (capacity)
# ARGV[2] = refill_rate (tokens per second)
# ARGV[3] = current time (seconds, float as string)
# ARGV[4] = tokens to consume (usually 1)
# Returns: [allowed (0/1), remaining_tokens, retry_after_seconds]
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- Refill tokens based on elapsed time
local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + elapsed * refill_rate)
last_refill = now

local allowed = 0
local retry_after = 0

if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
else
    retry_after = (requested - tokens) / refill_rate
end

redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 60)

return {allowed, math.floor(tokens), math.ceil(retry_after)}
"""


class RateLimiter:
    """Token-bucket rate limiter using Redis for distributed state.

    Args:
        max_tokens: Bucket capacity (burst size).
        refill_rate: Tokens added per second.
        key_prefix: Redis key namespace.
    """

    def __init__(
        self,
        max_tokens: int = 60,
        refill_rate: float = 1.0,
        key_prefix: str = "rl",
    ) -> None:
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.key_prefix = key_prefix
        self._script_sha: Optional[str] = None

    def _bucket_key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    async def _ensure_script(self, redis: Redis) -> str:
        if self._script_sha is None:
            self._script_sha = await redis.script_load(_TOKEN_BUCKET_LUA)
        return self._script_sha

    async def check(
        self, redis: Redis, identifier: str, tokens: int = 1
    ) -> tuple[bool, int, int]:
        """Check and consume tokens from the bucket.

        Args:
            redis: Async Redis client.
            identifier: Unique key for the client (e.g. user_id or IP).
            tokens: Number of tokens to consume.

        Returns:
            Tuple of (allowed, remaining, retry_after_seconds).
        """
        sha = await self._ensure_script(redis)
        now = time.time()
        try:
            result = await redis.evalsha(
                sha,
                1,
                self._bucket_key(identifier),
                str(self.max_tokens),
                str(self.refill_rate),
                str(now),
                str(tokens),
            )
            allowed, remaining, retry_after = int(result[0]), int(result[1]), int(result[2])
            return bool(allowed), remaining, retry_after
        except Exception:
            # If Redis is unavailable, fail open so detection still works.
            return True, self.max_tokens, 0


# ── Pre-configured limiters per role ────────────────────────────────────

_DEFAULT_LIMITERS: dict[str, RateLimiter] = {
    "user": RateLimiter(max_tokens=30, refill_rate=0.5, key_prefix="rl:user"),
    "service": RateLimiter(max_tokens=120, refill_rate=2.0, key_prefix="rl:svc"),
    "admin": RateLimiter(max_tokens=300, refill_rate=5.0, key_prefix="rl:admin"),
}


def rate_limit(
    max_tokens: int | None = None,
    refill_rate: float | None = None,
    key_prefix: str = "rl:custom",
):
    """Dependency factory that rate-limits by authenticated user or IP.

    When ``max_tokens`` / ``refill_rate`` are given a custom limiter is
    constructed.  Otherwise the request is routed to a role-based default.

    Usage::

        @router.post("/detect", dependencies=[Depends(rate_limit())])
        async def detect(): ...

        @router.post("/batch", dependencies=[Depends(rate_limit(max_tokens=5, refill_rate=0.1))])
        async def batch(): ...
    """

    custom_limiter: Optional[RateLimiter] = None
    if max_tokens is not None and refill_rate is not None:
        custom_limiter = RateLimiter(
            max_tokens=max_tokens, refill_rate=refill_rate, key_prefix=key_prefix
        )

    async def _dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        # Determine identifier: prefer authenticated user_id, fall back to IP.
        identifier: str = request.client.host if request.client else "unknown"
        role = "user"

        # If auth middleware already resolved the user, use it.
        user = getattr(request.state, "user", None)
        if user is not None:
            identifier = getattr(user, "user_id", identifier)
            role = getattr(user, "role", role)

        limiter = custom_limiter or _DEFAULT_LIMITERS.get(role, _DEFAULT_LIMITERS["user"])
        allowed, remaining, retry_after = await limiter.check(redis, identifier)

        # Always set informational headers.
        request.state.rate_limit_remaining = remaining

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {retry_after}s.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": str(remaining),
                },
            )

    return _dependency
