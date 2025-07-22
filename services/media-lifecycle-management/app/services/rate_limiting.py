#!/usr/bin/env python3
"""
Rate Limiting Service for the AIMA Media Lifecycle Management Service.

This module provides comprehensive rate limiting functionality including
token bucket, sliding window, and fixed window algorithms for controlling
API access, resource usage, and preventing abuse.
"""

import logging
import asyncio
import time
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import UUID
from collections import defaultdict, deque
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update

from ..core.redis_client import CacheManager
from ..core.database import User, MediaFile
from .audit_service import AuditService, AuditEventType, AuditSeverity
from .monitoring_service import MonitoringService
from ..middleware.error_handling import RateLimitExceededError


logger = logging.getLogger(__name__)


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(str, Enum):
    """Rate limit scopes."""
    GLOBAL = "global"
    USER = "user"
    IP = "ip"
    API_KEY = "api_key"
    ENDPOINT = "endpoint"
    RESOURCE = "resource"


class RateLimitAction(str, Enum):
    """Actions to take when rate limit is exceeded."""
    BLOCK = "block"
    THROTTLE = "throttle"
    LOG_ONLY = "log_only"
    CAPTCHA = "captcha"


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    name: str
    scope: RateLimitScope
    algorithm: RateLimitAlgorithm
    limit: int  # Number of requests/tokens
    window: int  # Time window in seconds
    action: RateLimitAction
    
    # Optional configurations
    burst_limit: Optional[int] = None  # For token bucket
    refill_rate: Optional[float] = None  # Tokens per second
    priority: int = 0  # Higher priority rules are checked first
    enabled: bool = True
    
    # Conditions
    endpoints: Optional[List[str]] = None
    methods: Optional[List[str]] = None
    user_roles: Optional[List[str]] = None
    
    # Penalties
    penalty_multiplier: float = 1.0
    penalty_duration: int = 0  # seconds
    
    def matches_request(self, endpoint: str, method: str, user_role: str = None) -> bool:
        """Check if rule matches the request."""
        if not self.enabled:
            return False
        
        if self.endpoints and endpoint not in self.endpoints:
            return False
        
        if self.methods and method not in self.methods:
            return False
        
        if self.user_roles and user_role not in self.user_roles:
            return False
        
        return True


@dataclass
class RateLimitState:
    """Current state of a rate limit."""
    key: str
    rule_name: str
    algorithm: RateLimitAlgorithm
    
    # Token bucket state
    tokens: float = 0.0
    last_refill: float = 0.0
    
    # Window-based state
    requests: List[float] = None  # Timestamps
    window_start: float = 0.0
    request_count: int = 0
    
    # Penalty state
    penalty_until: Optional[float] = None
    penalty_count: int = 0
    
    def __post_init__(self):
        if self.requests is None:
            self.requests = []
        if self.last_refill == 0.0:
            self.last_refill = time.time()


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    rule_name: str
    remaining: int
    reset_time: float
    retry_after: Optional[int] = None
    penalty_active: bool = False
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.remaining + (0 if self.allowed else 1)),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_time))
        }
        
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        
        if self.penalty_active:
            headers["X-RateLimit-Penalty"] = "true"
        
        return headers


class TokenBucketLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, rule: RateLimitRule):
        self.rule = rule
        self.capacity = rule.burst_limit or rule.limit
        self.refill_rate = rule.refill_rate or (rule.limit / rule.window)
    
    async def check_limit(self, state: RateLimitState, tokens_requested: int = 1) -> RateLimitResult:
        """Check if request is within rate limit."""
        current_time = time.time()
        
        # Refill tokens
        time_passed = current_time - state.last_refill
        tokens_to_add = time_passed * self.refill_rate
        state.tokens = min(self.capacity, state.tokens + tokens_to_add)
        state.last_refill = current_time
        
        # Check penalty
        if state.penalty_until and current_time < state.penalty_until:
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=state.penalty_until,
                retry_after=int(state.penalty_until - current_time),
                penalty_active=True
            )
        
        # Check if enough tokens available
        if state.tokens >= tokens_requested:
            state.tokens -= tokens_requested
            remaining = int(state.tokens)
            
            # Calculate reset time (when bucket will be full)
            tokens_needed = self.capacity - state.tokens
            reset_time = current_time + (tokens_needed / self.refill_rate)
            
            return RateLimitResult(
                allowed=True,
                rule_name=self.rule.name,
                remaining=remaining,
                reset_time=reset_time
            )
        else:
            # Apply penalty if configured
            if self.rule.penalty_duration > 0:
                state.penalty_count += 1
                penalty_duration = self.rule.penalty_duration * (self.rule.penalty_multiplier ** state.penalty_count)
                state.penalty_until = current_time + penalty_duration
            
            # Calculate when enough tokens will be available
            tokens_needed = tokens_requested - state.tokens
            retry_after = int(tokens_needed / self.refill_rate)
            
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=current_time + retry_after,
                retry_after=retry_after
            )


class SlidingWindowLimiter:
    """Sliding window rate limiter implementation."""
    
    def __init__(self, rule: RateLimitRule):
        self.rule = rule
    
    async def check_limit(self, state: RateLimitState) -> RateLimitResult:
        """Check if request is within rate limit."""
        current_time = time.time()
        window_start = current_time - self.rule.window
        
        # Check penalty
        if state.penalty_until and current_time < state.penalty_until:
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=state.penalty_until,
                retry_after=int(state.penalty_until - current_time),
                penalty_active=True
            )
        
        # Remove old requests outside the window
        state.requests = [req_time for req_time in state.requests if req_time > window_start]
        
        # Check if within limit
        if len(state.requests) < self.rule.limit:
            state.requests.append(current_time)
            remaining = self.rule.limit - len(state.requests)
            
            # Reset time is when the oldest request in window expires
            reset_time = (state.requests[0] + self.rule.window) if state.requests else current_time
            
            return RateLimitResult(
                allowed=True,
                rule_name=self.rule.name,
                remaining=remaining,
                reset_time=reset_time
            )
        else:
            # Apply penalty if configured
            if self.rule.penalty_duration > 0:
                state.penalty_count += 1
                penalty_duration = self.rule.penalty_duration * (self.rule.penalty_multiplier ** state.penalty_count)
                state.penalty_until = current_time + penalty_duration
            
            # Calculate retry after (when oldest request expires)
            oldest_request = min(state.requests)
            retry_after = int((oldest_request + self.rule.window) - current_time)
            
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=oldest_request + self.rule.window,
                retry_after=max(1, retry_after)
            )


class FixedWindowLimiter:
    """Fixed window rate limiter implementation."""
    
    def __init__(self, rule: RateLimitRule):
        self.rule = rule
    
    async def check_limit(self, state: RateLimitState) -> RateLimitResult:
        """Check if request is within rate limit."""
        current_time = time.time()
        window_start = math.floor(current_time / self.rule.window) * self.rule.window
        
        # Check penalty
        if state.penalty_until and current_time < state.penalty_until:
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=state.penalty_until,
                retry_after=int(state.penalty_until - current_time),
                penalty_active=True
            )
        
        # Reset counter if new window
        if state.window_start != window_start:
            state.window_start = window_start
            state.request_count = 0
        
        # Check if within limit
        if state.request_count < self.rule.limit:
            state.request_count += 1
            remaining = self.rule.limit - state.request_count
            reset_time = window_start + self.rule.window
            
            return RateLimitResult(
                allowed=True,
                rule_name=self.rule.name,
                remaining=remaining,
                reset_time=reset_time
            )
        else:
            # Apply penalty if configured
            if self.rule.penalty_duration > 0:
                state.penalty_count += 1
                penalty_duration = self.rule.penalty_duration * (self.rule.penalty_multiplier ** state.penalty_count)
                state.penalty_until = current_time + penalty_duration
            
            reset_time = window_start + self.rule.window
            retry_after = int(reset_time - current_time)
            
            return RateLimitResult(
                allowed=False,
                rule_name=self.rule.name,
                remaining=0,
                reset_time=reset_time,
                retry_after=max(1, retry_after)
            )


class RateLimitingService:
    """Main rate limiting service."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        audit_service: Optional[AuditService] = None,
        monitoring_service: Optional[MonitoringService] = None
    ):
        self.cache = cache_manager
        self.audit_service = audit_service
        self.monitoring_service = monitoring_service
        
        # Rate limit rules
        self.rules: Dict[str, RateLimitRule] = {}
        self.rule_priority_order: List[str] = []
        
        # Limiters
        self.limiters: Dict[RateLimitAlgorithm, Any] = {}
        
        # State cache (in-memory for performance)
        self.state_cache: Dict[str, RateLimitState] = {}
        self.cache_ttl = 3600  # 1 hour
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "throttled_requests": 0,
            "rules_triggered": defaultdict(int)
        }
        
        # Initialize default rules
        self._initialize_default_rules()
    
    def _initialize_default_rules(self):
        """Initialize default rate limiting rules."""
        default_rules = [
            # Global API rate limits
            RateLimitRule(
                name="global_api_limit",
                scope=RateLimitScope.GLOBAL,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                limit=10000,
                window=3600,  # 1 hour
                action=RateLimitAction.THROTTLE,
                priority=1
            ),
            
            # Per-user API limits
            RateLimitRule(
                name="user_api_limit",
                scope=RateLimitScope.USER,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                limit=1000,
                window=3600,  # 1 hour
                burst_limit=100,
                refill_rate=1000/3600,  # ~0.28 tokens per second
                action=RateLimitAction.BLOCK,
                priority=2
            ),
            
            # Per-IP limits
            RateLimitRule(
                name="ip_limit",
                scope=RateLimitScope.IP,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                limit=500,
                window=3600,  # 1 hour
                action=RateLimitAction.BLOCK,
                priority=3,
                penalty_duration=300,  # 5 minutes
                penalty_multiplier=2.0
            ),
            
            # Upload rate limits
            RateLimitRule(
                name="upload_limit",
                scope=RateLimitScope.USER,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                limit=50,
                window=3600,  # 1 hour
                burst_limit=10,
                action=RateLimitAction.BLOCK,
                endpoints=["/api/v1/media/upload"],
                priority=4
            ),
            
            # Processing job limits
            RateLimitRule(
                name="processing_limit",
                scope=RateLimitScope.USER,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                limit=20,
                window=3600,  # 1 hour
                action=RateLimitAction.BLOCK,
                endpoints=["/api/v1/processing/jobs"],
                priority=5
            ),
            
            # Authentication limits
            RateLimitRule(
                name="auth_limit",
                scope=RateLimitScope.IP,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                limit=10,
                window=900,  # 15 minutes
                action=RateLimitAction.BLOCK,
                endpoints=["/api/v1/auth/login", "/api/v1/auth/register"],
                priority=6,
                penalty_duration=1800,  # 30 minutes
                penalty_multiplier=3.0
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: RateLimitRule):
        """Add a rate limiting rule."""
        self.rules[rule.name] = rule
        
        # Update priority order
        self.rule_priority_order = sorted(
            self.rules.keys(),
            key=lambda name: self.rules[name].priority,
            reverse=True
        )
        
        logger.info(f"Added rate limit rule: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rate limiting rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.rule_priority_order = [name for name in self.rule_priority_order if name != rule_name]
            logger.info(f"Removed rate limit rule: {rule_name}")
            return True
        return False
    
    def update_rule(self, rule_name: str, **updates) -> bool:
        """Update a rate limiting rule."""
        if rule_name not in self.rules:
            return False
        
        rule = self.rules[rule_name]
        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        # Update priority order if priority changed
        if 'priority' in updates:
            self.rule_priority_order = sorted(
                self.rules.keys(),
                key=lambda name: self.rules[name].priority,
                reverse=True
            )
        
        logger.info(f"Updated rate limit rule: {rule_name}")
        return True
    
    async def check_rate_limit(
        self,
        db: AsyncSession,
        identifier: str,
        scope: RateLimitScope,
        endpoint: str = None,
        method: str = "GET",
        user_id: UUID = None,
        user_role: str = None,
        tokens_requested: int = 1
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.
        
        Args:
            db: Database session
            identifier: Unique identifier (IP, user ID, API key, etc.)
            scope: Rate limit scope
            endpoint: API endpoint
            method: HTTP method
            user_id: User ID for audit logging
            user_role: User role for rule matching
            tokens_requested: Number of tokens to consume
        
        Returns:
            RateLimitResult indicating if request is allowed
        """
        self.stats["total_requests"] += 1
        
        try:
            # Find applicable rules
            applicable_rules = self._find_applicable_rules(scope, endpoint, method, user_role)
            
            if not applicable_rules:
                # No rules apply, allow request
                return RateLimitResult(
                    allowed=True,
                    rule_name="no_rules",
                    remaining=float('inf'),
                    reset_time=time.time() + 3600
                )
            
            # Check each rule in priority order
            for rule in applicable_rules:
                result = await self._check_rule(
                    rule,
                    identifier,
                    scope,
                    tokens_requested
                )
                
                if not result.allowed:
                    # Rule violated, handle action
                    await self._handle_rate_limit_violation(
                        db,
                        rule,
                        identifier,
                        scope,
                        result,
                        user_id,
                        endpoint,
                        method
                    )
                    
                    return result
            
            # All rules passed, return the most restrictive result
            most_restrictive = applicable_rules[0]
            return await self._check_rule(
                most_restrictive,
                identifier,
                scope,
                tokens_requested
            )
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow request but log the issue
            return RateLimitResult(
                allowed=True,
                rule_name="error",
                remaining=0,
                reset_time=time.time() + 3600
            )
    
    def _find_applicable_rules(
        self,
        scope: RateLimitScope,
        endpoint: str,
        method: str,
        user_role: str
    ) -> List[RateLimitRule]:
        """Find rules that apply to the current request."""
        applicable_rules = []
        
        for rule_name in self.rule_priority_order:
            rule = self.rules[rule_name]
            
            # Check if rule scope matches
            if rule.scope != scope and rule.scope != RateLimitScope.GLOBAL:
                continue
            
            # Check if rule matches request
            if rule.matches_request(endpoint, method, user_role):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    async def _check_rule(
        self,
        rule: RateLimitRule,
        identifier: str,
        scope: RateLimitScope,
        tokens_requested: int
    ) -> RateLimitResult:
        """Check a specific rule against the request."""
        # Generate state key
        state_key = f"{rule.name}:{scope.value}:{identifier}"
        
        # Get or create state
        state = await self._get_rate_limit_state(state_key, rule)
        
        # Check limit based on algorithm
        if rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            limiter = TokenBucketLimiter(rule)
            result = await limiter.check_limit(state, tokens_requested)
        elif rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            limiter = SlidingWindowLimiter(rule)
            result = await limiter.check_limit(state)
        elif rule.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            limiter = FixedWindowLimiter(rule)
            result = await limiter.check_limit(state)
        else:
            # Default to sliding window
            limiter = SlidingWindowLimiter(rule)
            result = await limiter.check_limit(state)
        
        # Store updated state
        await self._store_rate_limit_state(state_key, state)
        
        return result
    
    async def _get_rate_limit_state(self, state_key: str, rule: RateLimitRule) -> RateLimitState:
        """Get rate limit state from cache."""
        # Try in-memory cache first
        if state_key in self.state_cache:
            return self.state_cache[state_key]
        
        # Try Redis cache
        try:
            cached_data = await self.cache.get(f"rate_limit_state:{state_key}")
            if cached_data:
                state_dict = json.loads(cached_data)
                state = RateLimitState(
                    key=state_dict["key"],
                    rule_name=state_dict["rule_name"],
                    algorithm=RateLimitAlgorithm(state_dict["algorithm"]),
                    tokens=state_dict.get("tokens", 0.0),
                    last_refill=state_dict.get("last_refill", time.time()),
                    requests=state_dict.get("requests", []),
                    window_start=state_dict.get("window_start", 0.0),
                    request_count=state_dict.get("request_count", 0),
                    penalty_until=state_dict.get("penalty_until"),
                    penalty_count=state_dict.get("penalty_count", 0)
                )
                
                # Cache in memory
                self.state_cache[state_key] = state
                return state
        except Exception as e:
            logger.warning(f"Failed to load rate limit state from cache: {e}")
        
        # Create new state
        state = RateLimitState(
            key=state_key,
            rule_name=rule.name,
            algorithm=rule.algorithm
        )
        
        # Initialize based on algorithm
        if rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            state.tokens = rule.burst_limit or rule.limit
            state.last_refill = time.time()
        
        self.state_cache[state_key] = state
        return state
    
    async def _store_rate_limit_state(self, state_key: str, state: RateLimitState):
        """Store rate limit state in cache."""
        # Update in-memory cache
        self.state_cache[state_key] = state
        
        # Store in Redis
        try:
            state_dict = {
                "key": state.key,
                "rule_name": state.rule_name,
                "algorithm": state.algorithm.value,
                "tokens": state.tokens,
                "last_refill": state.last_refill,
                "requests": state.requests,
                "window_start": state.window_start,
                "request_count": state.request_count,
                "penalty_until": state.penalty_until,
                "penalty_count": state.penalty_count
            }
            
            await self.cache.set(
                f"rate_limit_state:{state_key}",
                json.dumps(state_dict),
                ttl=self.cache_ttl
            )
        except Exception as e:
            logger.warning(f"Failed to store rate limit state in cache: {e}")
    
    async def _handle_rate_limit_violation(
        self,
        db: AsyncSession,
        rule: RateLimitRule,
        identifier: str,
        scope: RateLimitScope,
        result: RateLimitResult,
        user_id: Optional[UUID],
        endpoint: str,
        method: str
    ):
        """Handle rate limit violation."""
        self.stats["rules_triggered"][rule.name] += 1
        
        if rule.action == RateLimitAction.BLOCK:
            self.stats["blocked_requests"] += 1
        elif rule.action == RateLimitAction.THROTTLE:
            self.stats["throttled_requests"] += 1
        
        # Log audit event
        if self.audit_service:
            from .audit_service import AuditContext, AuditEvent
            
            audit_context = AuditContext(
                user_id=user_id,
                ip_address=identifier if scope == RateLimitScope.IP else None
            )
            
            audit_event = AuditEvent(
                event_type=AuditEventType.SECURITY_RATE_LIMIT_EXCEEDED,
                severity=AuditSeverity.MEDIUM,
                status="blocked" if rule.action == RateLimitAction.BLOCK else "throttled",
                message=f"Rate limit exceeded: {rule.name}",
                context=audit_context,
                details={
                    "rule_name": rule.name,
                    "scope": scope.value,
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "method": method,
                    "action": rule.action.value,
                    "remaining": result.remaining,
                    "retry_after": result.retry_after
                }
            )
            
            await self.audit_service.log_event(db, audit_event)
        
        # Record metrics
        if self.monitoring_service:
            await self.monitoring_service.record_metric(
                f"rate_limit.{rule.name}.violations",
                1
            )
            await self.monitoring_service.record_metric(
                f"rate_limit.{scope.value}.violations",
                1
            )
        
        logger.warning(
            f"Rate limit exceeded - Rule: {rule.name}, Scope: {scope.value}, "
            f"Identifier: {identifier}, Action: {rule.action.value}"
        )
    
    async def reset_rate_limit(
        self,
        identifier: str,
        scope: RateLimitScope,
        rule_name: Optional[str] = None
    ) -> bool:
        """Reset rate limit for identifier."""
        try:
            if rule_name:
                # Reset specific rule
                state_key = f"{rule_name}:{scope.value}:{identifier}"
                await self._clear_rate_limit_state(state_key)
            else:
                # Reset all rules for identifier
                pattern = f"*:{scope.value}:{identifier}"
                keys = await self.cache.scan_keys(f"rate_limit_state:{pattern}")
                
                for key in keys:
                    state_key = key.replace("rate_limit_state:", "")
                    await self._clear_rate_limit_state(state_key)
            
            logger.info(f"Reset rate limit for {scope.value}:{identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False
    
    async def _clear_rate_limit_state(self, state_key: str):
        """Clear rate limit state."""
        # Remove from in-memory cache
        if state_key in self.state_cache:
            del self.state_cache[state_key]
        
        # Remove from Redis
        await self.cache.delete(f"rate_limit_state:{state_key}")
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        scope: RateLimitScope
    ) -> Dict[str, Any]:
        """Get current rate limit status for identifier."""
        status = {
            "identifier": identifier,
            "scope": scope.value,
            "rules": {}
        }
        
        try:
            for rule_name, rule in self.rules.items():
                if rule.scope == scope or rule.scope == RateLimitScope.GLOBAL:
                    state_key = f"{rule_name}:{scope.value}:{identifier}"
                    state = await self._get_rate_limit_state(state_key, rule)
                    
                    rule_status = {
                        "limit": rule.limit,
                        "window": rule.window,
                        "algorithm": rule.algorithm.value,
                        "action": rule.action.value
                    }
                    
                    if rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                        rule_status["tokens"] = state.tokens
                        rule_status["capacity"] = rule.burst_limit or rule.limit
                    elif rule.algorithm in [RateLimitAlgorithm.SLIDING_WINDOW, RateLimitAlgorithm.FIXED_WINDOW]:
                        if rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                            current_time = time.time()
                            window_start = current_time - rule.window
                            current_requests = len([req for req in state.requests if req > window_start])
                        else:
                            current_requests = state.request_count
                        
                        rule_status["current_requests"] = current_requests
                        rule_status["remaining"] = max(0, rule.limit - current_requests)
                    
                    if state.penalty_until:
                        rule_status["penalty_until"] = state.penalty_until
                        rule_status["penalty_active"] = time.time() < state.penalty_until
                    
                    status["rules"][rule_name] = rule_status
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get rate limit status: {e}")
            return {"error": str(e)}
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        total_requests = self.stats["total_requests"]
        blocked_requests = self.stats["blocked_requests"]
        throttled_requests = self.stats["throttled_requests"]
        
        return {
            "total_requests": total_requests,
            "allowed_requests": total_requests - blocked_requests - throttled_requests,
            "blocked_requests": blocked_requests,
            "throttled_requests": throttled_requests,
            "block_rate": (blocked_requests / total_requests * 100) if total_requests > 0 else 0,
            "throttle_rate": (throttled_requests / total_requests * 100) if total_requests > 0 else 0,
            "rules_triggered": dict(self.stats["rules_triggered"]),
            "active_rules": len(self.rules),
            "cache_size": len(self.state_cache),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def cleanup_expired_states(self):
        """Clean up expired rate limit states."""
        try:
            current_time = time.time()
            expired_keys = []
            
            # Check in-memory cache
            for state_key, state in self.state_cache.items():
                # Remove states that haven't been accessed recently
                if (state.penalty_until and current_time > state.penalty_until and
                    current_time - state.last_refill > self.cache_ttl):
                    expired_keys.append(state_key)
            
            # Remove expired states
            for key in expired_keys:
                del self.state_cache[key]
                await self.cache.delete(f"rate_limit_state:{key}")
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired rate limit states")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired states: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of the rate limiting service."""
        try:
            # Test basic functionality
            test_result = await self.check_rate_limit(
                db=None,  # Not needed for test
                identifier="health_check",
                scope=RateLimitScope.IP,
                endpoint="/health",
                method="GET"
            )
            
            stats = await self.get_statistics()
            
            return {
                "status": "healthy",
                "test_passed": test_result.allowed,
                "active_rules": len(self.rules),
                "cache_size": len(self.state_cache),
                "statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Utility functions for common rate limiting scenarios

async def check_api_rate_limit(
    rate_limiter: RateLimitingService,
    db: AsyncSession,
    user_id: Optional[UUID],
    ip_address: str,
    endpoint: str,
    method: str = "GET"
) -> RateLimitResult:
    """Check API rate limits for a request."""
    # Check IP-based limits first
    ip_result = await rate_limiter.check_rate_limit(
        db=db,
        identifier=ip_address,
        scope=RateLimitScope.IP,
        endpoint=endpoint,
        method=method,
        user_id=user_id
    )
    
    if not ip_result.allowed:
        return ip_result
    
    # Check user-based limits if authenticated
    if user_id:
        user_result = await rate_limiter.check_rate_limit(
            db=db,
            identifier=str(user_id),
            scope=RateLimitScope.USER,
            endpoint=endpoint,
            method=method,
            user_id=user_id
        )
        
        if not user_result.allowed:
            return user_result
    
    # Return the most restrictive result
    return ip_result


async def check_upload_rate_limit(
    rate_limiter: RateLimitingService,
    db: AsyncSession,
    user_id: UUID,
    file_size: int
) -> RateLimitResult:
    """Check upload rate limits based on file size."""
    # Calculate tokens based on file size (1 token per MB)
    tokens_requested = max(1, file_size // (1024 * 1024))
    
    return await rate_limiter.check_rate_limit(
        db=db,
        identifier=str(user_id),
        scope=RateLimitScope.USER,
        endpoint="/api/v1/media/upload",
        method="POST",
        user_id=user_id,
        tokens_requested=tokens_requested
    )