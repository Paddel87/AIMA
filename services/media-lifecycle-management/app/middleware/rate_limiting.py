#!/usr/bin/env python3
"""
Rate limiting middleware for the AIMA Media Lifecycle Management Service.

This middleware implements various rate limiting strategies to protect
the service from abuse and ensure fair usage across all clients.
"""

import time
import asyncio
from typing import Callable, Dict, Any, Optional, Tuple
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import status
import structlog

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: int, retry_after: int = None):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {limit} requests per {window} seconds")


class TokenBucket:
    """Token bucket algorithm for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket."""
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    async def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait before tokens are available."""
        async with self._lock:
            if self.tokens >= tokens:
                return 0
            
            needed_tokens = tokens - self.tokens
            return needed_tokens / self.refill_rate


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""
    
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window  # window size in seconds
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> Tuple[bool, int]:
        """Check if request is allowed and return remaining count."""
        async with self._lock:
            now = time.time()
            
            # Remove old requests outside the window
            while self.requests and self.requests[0] <= now - self.window:
                self.requests.popleft()
            
            # Check if we're within the limit
            if len(self.requests) < self.limit:
                self.requests.append(now)
                return True, self.limit - len(self.requests)
            
            return False, 0
    
    async def get_reset_time(self) -> int:
        """Get time when the window resets."""
        async with self._lock:
            if not self.requests:
                return int(time.time())
            
            return int(self.requests[0] + self.window)


class FixedWindowCounter:
    """Fixed window counter for rate limiting."""
    
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.count = 0
        self.window_start = time.time()
        self._lock = asyncio.Lock()
    
    async def is_allowed(self) -> Tuple[bool, int]:
        """Check if request is allowed and return remaining count."""
        async with self._lock:
            now = time.time()
            
            # Reset window if expired
            if now - self.window_start >= self.window:
                self.count = 0
                self.window_start = now
            
            # Check if we're within the limit
            if self.count < self.limit:
                self.count += 1
                return True, self.limit - self.count
            
            return False, 0
    
    async def get_reset_time(self) -> int:
        """Get time when the window resets."""
        return int(self.window_start + self.window)


class RateLimiter:
    """Main rate limiter with multiple strategies."""
    
    def __init__(self):
        self.limiters: Dict[str, Any] = {}
        self.global_limiters: Dict[str, Any] = {}
    
    def create_token_bucket(self, key: str, capacity: int, refill_rate: float) -> TokenBucket:
        """Create or get a token bucket limiter."""
        if key not in self.limiters:
            self.limiters[key] = TokenBucket(capacity, refill_rate)
        return self.limiters[key]
    
    def create_sliding_window(self, key: str, limit: int, window: int) -> SlidingWindowCounter:
        """Create or get a sliding window limiter."""
        if key not in self.limiters:
            self.limiters[key] = SlidingWindowCounter(limit, window)
        return self.limiters[key]
    
    def create_fixed_window(self, key: str, limit: int, window: int) -> FixedWindowCounter:
        """Create or get a fixed window limiter."""
        if key not in self.limiters:
            self.limiters[key] = FixedWindowCounter(limit, window)
        return self.limiters[key]
    
    async def check_rate_limit(self, key: str, limiter_type: str, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for a given key."""
        if limiter_type == "token_bucket":
            limiter = self.create_token_bucket(
                key, 
                kwargs.get("capacity", 100), 
                kwargs.get("refill_rate", 1.0)
            )
            allowed = await limiter.consume(kwargs.get("tokens", 1))
            wait_time = await limiter.get_wait_time(kwargs.get("tokens", 1))
            
            return allowed, {
                "wait_time": wait_time,
                "limiter_type": "token_bucket"
            }
        
        elif limiter_type == "sliding_window":
            limiter = self.create_sliding_window(
                key,
                kwargs.get("limit", 100),
                kwargs.get("window", 3600)
            )
            allowed, remaining = await limiter.is_allowed()
            reset_time = await limiter.get_reset_time()
            
            return allowed, {
                "remaining": remaining,
                "reset_time": reset_time,
                "limiter_type": "sliding_window"
            }
        
        elif limiter_type == "fixed_window":
            limiter = self.create_fixed_window(
                key,
                kwargs.get("limit", 100),
                kwargs.get("window", 3600)
            )
            allowed, remaining = await limiter.is_allowed()
            reset_time = await limiter.get_reset_time()
            
            return allowed, {
                "remaining": remaining,
                "reset_time": reset_time,
                "limiter_type": "fixed_window"
            }
        
        else:
            raise ValueError(f"Unknown limiter type: {limiter_type}")
    
    def cleanup_expired(self):
        """Clean up expired limiters to prevent memory leaks."""
        # This would be called periodically to clean up old limiters
        # Implementation depends on the specific use case
        pass


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware for applying rate limits to requests."""
    
    def __init__(
        self,
        app,
        limiter: RateLimiter = None,
        default_limit: int = 1000,
        default_window: int = 3600,
        limiter_type: str = "sliding_window",
        key_func: Callable[[Request], str] = None
    ):
        super().__init__(app)
        self.limiter = limiter or rate_limiter
        self.default_limit = default_limit
        self.default_window = default_window
        self.limiter_type = limiter_type
        self.key_func = key_func or self._default_key_func
        
        # Endpoint-specific rate limits
        self.endpoint_limits = {
            "/api/v1/media/upload": {"limit": 50, "window": 3600},  # 50 uploads per hour
            "/api/v1/media/process": {"limit": 100, "window": 3600},  # 100 processing requests per hour
            "/api/v1/auth/login": {"limit": 10, "window": 900},  # 10 login attempts per 15 minutes
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting to requests."""
        # Generate rate limit key
        key = self.key_func(request)
        
        # Get rate limit configuration for this endpoint
        endpoint_config = self._get_endpoint_config(request.url.path)
        
        try:
            # Check rate limit
            allowed, info = await self.limiter.check_rate_limit(
                key=key,
                limiter_type=self.limiter_type,
                **endpoint_config
            )
            
            if not allowed:
                return await self._create_rate_limit_response(request, info, endpoint_config)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            self._add_rate_limit_headers(response, info, endpoint_config)
            
            return response
            
        except Exception as e:
            logger.error(
                "Rate limiting error",
                error=str(e),
                key=key,
                path=request.url.path
            )
            
            # Continue without rate limiting if there's an error
            return await call_next(request)
    
    def _default_key_func(self, request: Request) -> str:
        """Default function to generate rate limit key."""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}:{request.url.path}"
        
        # Fallback to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}:{request.url.path}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_endpoint_config(self, path: str) -> Dict[str, Any]:
        """Get rate limit configuration for endpoint."""
        # Check for exact match
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        # Check for pattern matches
        for pattern, config in self.endpoint_limits.items():
            if self._path_matches_pattern(path, pattern):
                return config
        
        # Return default configuration
        return {
            "limit": self.default_limit,
            "window": self.default_window
        }
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern."""
        # Simple pattern matching - can be enhanced with regex
        if "*" in pattern:
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                return path.startswith(prefix) and path.endswith(suffix)
        
        return path == pattern
    
    async def _create_rate_limit_response(self, request: Request, info: Dict[str, Any], config: Dict[str, Any]) -> JSONResponse:
        """Create rate limit exceeded response."""
        retry_after = info.get("wait_time", info.get("reset_time", 60))
        
        response_data = {
            "error": True,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded. Limit: {config['limit']} requests per {config['window']} seconds",
            "limit": config["limit"],
            "window": config["window"],
            "retry_after": int(retry_after),
            "limiter_type": info.get("limiter_type"),
            "timestamp": time.time()
        }
        
        # Add remaining count if available
        if "remaining" in info:
            response_data["remaining"] = info["remaining"]
        
        # Log rate limit violation
        logger.warning(
            "Rate limit exceeded",
            path=request.url.path,
            method=request.method,
            client_ip=self._get_client_ip(request),
            limit=config["limit"],
            window=config["window"]
        )
        
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=response_data
        )
        
        # Add standard rate limit headers
        response.headers["Retry-After"] = str(int(retry_after))
        response.headers["X-RateLimit-Limit"] = str(config["limit"])
        response.headers["X-RateLimit-Window"] = str(config["window"])
        
        if "remaining" in info:
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        
        if "reset_time" in info:
            response.headers["X-RateLimit-Reset"] = str(info["reset_time"])
        
        return response
    
    def _add_rate_limit_headers(self, response: Response, info: Dict[str, Any], config: Dict[str, Any]):
        """Add rate limit headers to successful responses."""
        response.headers["X-RateLimit-Limit"] = str(config["limit"])
        response.headers["X-RateLimit-Window"] = str(config["window"])
        
        if "remaining" in info:
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        
        if "reset_time" in info:
            response.headers["X-RateLimit-Reset"] = str(info["reset_time"])


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return rate_limiter