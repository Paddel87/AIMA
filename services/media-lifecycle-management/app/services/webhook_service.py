#!/usr/bin/env python3
"""
Webhook Service for the AIMA Media Lifecycle Management Service.

This module handles webhook subscriptions, event delivery, and notification management.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from ..core.database import WebhookSubscription, WebhookDelivery
from ..core.redis_client import CacheManager
from ..models.webhooks import (
    WebhookEventType, WebhookDeliveryStatus, WebhookSubscriptionStatus,
    WebhookEventData, MediaEventData, ProcessingJobEventData,
    StorageEventData, SystemEventData, WebhookPayload
)
from ..models.media import MediaType, MediaStatus, ProcessingOperation
from ..models.common import ProcessingStatus
from ..middleware.error_handling import MediaServiceException


logger = logging.getLogger(__name__)


class WebhookService:
    """Service for managing webhooks and event notifications."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        max_retry_attempts: int = 3,
        retry_delay_seconds: int = 60,
        timeout_seconds: int = 30
    ):
        self.cache = cache_manager
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.timeout_seconds = timeout_seconds
        
        # HTTP client for webhook delivery
        self.http_client: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize the webhook service."""
        self.http_client = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout_seconds),
            headers={"User-Agent": "AIMA-Media-Lifecycle-Service/1.0"}
        )
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.http_client:
            await self.http_client.close()
    
    async def create_subscription(
        self,
        db: AsyncSession,
        user_id: UUID,
        url: str,
        events: List[WebhookEventType],
        name: Optional[str] = None,
        description: Optional[str] = None,
        secret: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        retry_delay_seconds: int = 60
    ) -> UUID:
        """
        Create a new webhook subscription.
        """
        try:
            subscription_id = uuid4()
            
            subscription = WebhookSubscription(
                id=subscription_id,
                user_id=user_id,
                url=url,
                events=events,
                name=name,
                description=description,
                secret=secret,
                filters=filters or {},
                timeout_seconds=timeout_seconds,
                retry_attempts=retry_attempts,
                retry_delay_seconds=retry_delay_seconds,
                status=WebhookSubscriptionStatus.ACTIVE,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(subscription)
            await db.commit()
            
            # Cache active subscriptions
            await self._cache_subscription(subscription)
            
            logger.info(f"Created webhook subscription {subscription_id} for user {user_id}")
            
            return subscription_id
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to create webhook subscription: {e}")
            raise MediaServiceException(f"Subscription creation failed: {str(e)}")
    
    async def update_subscription(
        self,
        db: AsyncSession,
        subscription_id: UUID,
        user_id: UUID,
        **updates
    ) -> bool:
        """
        Update a webhook subscription.
        """
        try:
            # Get subscription
            result = await db.execute(
                select(WebhookSubscription)
                .where(
                    and_(
                        WebhookSubscription.id == subscription_id,
                        WebhookSubscription.user_id == user_id
                    )
                )
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                raise MediaServiceException("Subscription not found or access denied")
            
            # Update fields
            for field, value in updates.items():
                if hasattr(subscription, field) and value is not None:
                    setattr(subscription, field, value)
            
            subscription.updated_at = datetime.utcnow()
            
            await db.commit()
            
            # Update cache
            await self._cache_subscription(subscription)
            
            logger.info(f"Updated webhook subscription {subscription_id}")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update webhook subscription {subscription_id}: {e}")
            raise MediaServiceException(f"Subscription update failed: {str(e)}")
    
    async def delete_subscription(
        self,
        db: AsyncSession,
        subscription_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete a webhook subscription.
        """
        try:
            # Get subscription
            result = await db.execute(
                select(WebhookSubscription)
                .where(
                    and_(
                        WebhookSubscription.id == subscription_id,
                        WebhookSubscription.user_id == user_id
                    )
                )
            )
            subscription = result.scalar_one_or_none()
            
            if not subscription:
                raise MediaServiceException("Subscription not found or access denied")
            
            # Delete subscription
            await db.delete(subscription)
            await db.commit()
            
            # Remove from cache
            await self.cache.delete(f"webhook_subscription:{subscription_id}")
            
            logger.info(f"Deleted webhook subscription {subscription_id}")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete webhook subscription {subscription_id}: {e}")
            raise MediaServiceException(f"Subscription deletion failed: {str(e)}")
    
    async def send_media_uploaded_event(
        self,
        file_id: UUID,
        user_id: UUID,
        filename: str,
        file_size: int,
        media_type: MediaType = MediaType.OTHER,
        mime_type: str = "application/octet-stream"
    ) -> None:
        """
        Send media uploaded event to subscribers.
        """
        event_data = MediaEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.MEDIA_UPLOADED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            file_id=file_id,
            filename=filename,
            media_type=media_type,
            status=MediaStatus.PROCESSING,
            owner_id=user_id,
            file_size=file_size,
            mime_type=mime_type
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_media_processing_completed_event(
        self,
        file_id: UUID,
        user_id: UUID,
        filename: str,
        download_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None
    ) -> None:
        """
        Send media processing completed event.
        """
        event_data = MediaEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.MEDIA_PROCESSING_COMPLETED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            file_id=file_id,
            filename=filename,
            media_type=MediaType.OTHER,  # Would be determined from DB
            status=MediaStatus.READY,
            owner_id=user_id,
            file_size=0,  # Would be from DB
            mime_type="",  # Would be from DB
            download_url=download_url,
            thumbnail_url=thumbnail_url
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_media_deleted_event(
        self,
        file_id: UUID,
        user_id: UUID,
        permanent: bool = False
    ) -> None:
        """
        Send media deleted event.
        """
        event_data = MediaEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.MEDIA_DELETED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            file_id=file_id,
            filename="",  # Would be from DB
            media_type=MediaType.OTHER,
            status=MediaStatus.DELETED,
            owner_id=user_id,
            file_size=0,
            mime_type=""
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_media_archived_event(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> None:
        """
        Send media archived event.
        """
        event_data = MediaEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.MEDIA_ARCHIVED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            file_id=file_id,
            filename="",
            media_type=MediaType.OTHER,
            status=MediaStatus.ARCHIVED,
            owner_id=user_id,
            file_size=0,
            mime_type=""
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_media_expired_event(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> None:
        """
        Send media expired event.
        """
        event_data = MediaEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.MEDIA_EXPIRED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            file_id=file_id,
            filename="",
            media_type=MediaType.OTHER,
            status=MediaStatus.DELETED,
            owner_id=user_id,
            file_size=0,
            mime_type=""
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_job_started_event(
        self,
        job_id: UUID,
        file_id: UUID,
        operation: ProcessingOperation
    ) -> None:
        """
        Send processing job started event.
        """
        event_data = ProcessingJobEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.JOB_STARTED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            job_id=job_id,
            file_id=file_id,
            operation=operation,
            status=ProcessingStatus.RUNNING,
            priority=5
        )
        
        await self._dispatch_event(event_data)
    
    async def send_job_completed_event(
        self,
        job_id: UUID,
        file_id: UUID,
        operation: ProcessingOperation,
        result_url: Optional[str] = None
    ) -> None:
        """
        Send processing job completed event.
        """
        event_data = ProcessingJobEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.JOB_COMPLETED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            job_id=job_id,
            file_id=file_id,
            operation=operation,
            status=ProcessingStatus.COMPLETED,
            priority=5,
            result_url=result_url
        )
        
        await self._dispatch_event(event_data)
    
    async def send_job_failed_event(
        self,
        job_id: UUID,
        file_id: UUID,
        operation: ProcessingOperation,
        error_message: str
    ) -> None:
        """
        Send processing job failed event.
        """
        event_data = ProcessingJobEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.JOB_FAILED,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            job_id=job_id,
            file_id=file_id,
            operation=operation,
            status=ProcessingStatus.FAILED,
            priority=5,
            error_message=error_message
        )
        
        await self._dispatch_event(event_data)
    
    async def send_storage_quota_warning_event(
        self,
        user_id: UUID,
        total_size: int,
        quota: int,
        threshold_percentage: float
    ) -> None:
        """
        Send storage quota warning event.
        """
        event_data = StorageEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.STORAGE_QUOTA_WARNING,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            user_id=user_id,
            total_size=total_size,
            quota=quota,
            quota_used_percentage=(total_size / quota) * 100,
            threshold_percentage=threshold_percentage
        )
        
        await self._dispatch_event(event_data, user_id)
    
    async def send_system_health_check_event(
        self,
        service_name: str,
        health_status: str,
        response_time: float,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send system health check event.
        """
        event_data = SystemEventData(
            event_id=uuid4(),
            event_type=WebhookEventType.SYSTEM_HEALTH_CHECK,
            timestamp=datetime.utcnow(),
            source="media-lifecycle-service",
            service_name=service_name,
            severity="info",
            message=f"Health check for {service_name}: {health_status}",
            health_status=health_status,
            response_time=response_time,
            details=details
        )
        
        await self._dispatch_event(event_data)
    
    async def _dispatch_event(
        self,
        event_data: WebhookEventData,
        user_id: Optional[UUID] = None
    ) -> None:
        """
        Dispatch an event to all matching subscribers.
        """
        try:
            # Get matching subscriptions
            subscriptions = await self._get_matching_subscriptions(
                event_data.event_type,
                user_id
            )
            
            # Create delivery tasks
            delivery_tasks = []
            
            for subscription in subscriptions:
                if self._event_matches_filters(event_data, subscription.get("filters", {})):
                    task = asyncio.create_task(
                        self._deliver_webhook(
                            subscription_id=UUID(subscription["id"]),
                            event_data=event_data,
                            url=subscription["url"],
                            secret=subscription.get("secret"),
                            timeout_seconds=subscription.get("timeout_seconds", 30),
                            retry_attempts=subscription.get("retry_attempts", 3)
                        )
                    )
                    delivery_tasks.append(task)
            
            # Execute deliveries concurrently
            if delivery_tasks:
                await asyncio.gather(*delivery_tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Failed to dispatch event {event_data.event_id}: {e}")
    
    async def _get_matching_subscriptions(
        self,
        event_type: WebhookEventType,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Get subscriptions that match the event type and user.
        """
        try:
            # Try to get from cache first
            cache_key = f"webhook_subscriptions:{event_type}"
            if user_id:
                cache_key += f":{user_id}"
            
            cached_subscriptions = await self.cache.get(cache_key)
            if cached_subscriptions:
                return cached_subscriptions
            
            # If not in cache, we would query the database
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to get matching subscriptions: {e}")
            return []
    
    def _event_matches_filters(
        self,
        event_data: WebhookEventData,
        filters: Dict[str, Any]
    ) -> bool:
        """
        Check if an event matches the subscription filters.
        """
        if not filters:
            return True
        
        try:
            # Check media type filter
            if "media_types" in filters and hasattr(event_data, "media_type"):
                if event_data.media_type not in filters["media_types"]:
                    return False
            
            # Check file size filter
            if "min_file_size" in filters and hasattr(event_data, "file_size"):
                if event_data.file_size < filters["min_file_size"]:
                    return False
            
            if "max_file_size" in filters and hasattr(event_data, "file_size"):
                if event_data.file_size > filters["max_file_size"]:
                    return False
            
            # Check operation filter
            if "operations" in filters and hasattr(event_data, "operation"):
                if event_data.operation not in filters["operations"]:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking event filters: {e}")
            return True  # Default to allowing the event
    
    async def _deliver_webhook(
        self,
        subscription_id: UUID,
        event_data: WebhookEventData,
        url: str,
        secret: Optional[str] = None,
        timeout_seconds: int = 30,
        retry_attempts: int = 3
    ) -> None:
        """
        Deliver a webhook to a specific subscription.
        """
        delivery_id = uuid4()
        attempt = 1
        
        while attempt <= retry_attempts + 1:
            try:
                # Create webhook payload
                payload = WebhookPayload(
                    webhook_id=delivery_id,
                    subscription_id=subscription_id,
                    delivery_attempt=attempt,
                    data=event_data,
                    signature="",  # Will be calculated below
                    timestamp=datetime.utcnow()
                )
                
                # Serialize payload
                payload_json = payload.model_dump_json()
                
                # Calculate signature
                if secret:
                    signature = self._calculate_signature(payload_json, secret)
                    payload.signature = signature
                    payload_json = payload.model_dump_json()
                
                # Prepare headers
                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-ID": str(delivery_id),
                    "X-Webhook-Timestamp": str(int(payload.timestamp.timestamp())),
                    "X-Webhook-Signature": payload.signature if secret else ""
                }
                
                # Make HTTP request
                start_time = datetime.utcnow()
                
                if not self.http_client:
                    await self.initialize()
                
                async with self.http_client.post(
                    url,
                    data=payload_json,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds)
                ) as response:
                    end_time = datetime.utcnow()
                    duration = (end_time - start_time).total_seconds()
                    
                    response_body = await response.text()
                    
                    # Log delivery attempt
                    await self._log_delivery_attempt(
                        delivery_id=delivery_id,
                        subscription_id=subscription_id,
                        event_id=event_data.event_id,
                        event_type=event_data.event_type,
                        url=url,
                        attempt=attempt,
                        status=WebhookDeliveryStatus.DELIVERED if response.status < 400 else WebhookDeliveryStatus.FAILED,
                        http_status_code=response.status,
                        response_headers=dict(response.headers),
                        response_body=response_body[:1000],  # Limit response body size
                        request_duration=duration
                    )
                    
                    if response.status < 400:
                        logger.info(
                            f"Webhook delivered successfully: {delivery_id} to {url} "
                            f"(attempt {attempt}, status {response.status})"
                        )
                        return
                    else:
                        logger.warning(
                            f"Webhook delivery failed: {delivery_id} to {url} "
                            f"(attempt {attempt}, status {response.status})"
                        )
            
            except Exception as e:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds() if 'start_time' in locals() else 0
                
                # Log delivery attempt
                await self._log_delivery_attempt(
                    delivery_id=delivery_id,
                    subscription_id=subscription_id,
                    event_id=event_data.event_id,
                    event_type=event_data.event_type,
                    url=url,
                    attempt=attempt,
                    status=WebhookDeliveryStatus.FAILED,
                    error_message=str(e),
                    request_duration=duration
                )
                
                logger.error(
                    f"Webhook delivery error: {delivery_id} to {url} "
                    f"(attempt {attempt}): {e}"
                )
            
            # Wait before retry
            if attempt <= retry_attempts:
                await asyncio.sleep(self.retry_delay_seconds)
            
            attempt += 1
        
        logger.error(
            f"Webhook delivery failed after {retry_attempts + 1} attempts: "
            f"{delivery_id} to {url}"
        )
    
    def _calculate_signature(self, payload: str, secret: str) -> str:
        """
        Calculate HMAC signature for webhook payload.
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _log_delivery_attempt(
        self,
        delivery_id: UUID,
        subscription_id: UUID,
        event_id: UUID,
        event_type: WebhookEventType,
        url: str,
        attempt: int,
        status: WebhookDeliveryStatus,
        http_status_code: Optional[int] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_body: Optional[str] = None,
        error_message: Optional[str] = None,
        request_duration: Optional[float] = None
    ) -> None:
        """
        Log a webhook delivery attempt.
        """
        try:
            # Store delivery log in cache for now
            # In a real implementation, this would go to the database
            delivery_log = {
                "id": str(delivery_id),
                "subscription_id": str(subscription_id),
                "event_id": str(event_id),
                "event_type": event_type,
                "url": url,
                "attempt": attempt,
                "status": status,
                "http_status_code": http_status_code,
                "response_headers": response_headers,
                "response_body": response_body,
                "error_message": error_message,
                "request_duration": request_duration,
                "created_at": datetime.utcnow().isoformat()
            }
            
            await self.cache.set(
                f"webhook_delivery:{delivery_id}:{attempt}",
                delivery_log,
                ttl=86400 * 7  # Keep for 7 days
            )
            
        except Exception as e:
            logger.error(f"Failed to log webhook delivery attempt: {e}")
    
    async def _cache_subscription(self, subscription: WebhookSubscription) -> None:
        """
        Cache a webhook subscription for fast lookup.
        """
        try:
            subscription_data = {
                "id": str(subscription.id),
                "user_id": str(subscription.user_id),
                "url": subscription.url,
                "events": subscription.events,
                "secret": subscription.secret,
                "filters": subscription.filters,
                "timeout_seconds": subscription.timeout_seconds,
                "retry_attempts": subscription.retry_attempts,
                "is_active": subscription.is_active
            }
            
            # Cache by subscription ID
            await self.cache.set(
                f"webhook_subscription:{subscription.id}",
                subscription_data,
                ttl=3600  # 1 hour
            )
            
            # Cache by event types for fast lookup
            for event_type in subscription.events:
                cache_key = f"webhook_subscriptions:{event_type}:{subscription.user_id}"
                
                # Get existing subscriptions for this event type
                existing = await self.cache.get(cache_key) or []
                
                # Add this subscription if not already present
                if not any(sub["id"] == str(subscription.id) for sub in existing):
                    existing.append(subscription_data)
                    await self.cache.set(cache_key, existing, ttl=3600)
            
        except Exception as e:
            logger.error(f"Failed to cache webhook subscription: {e}")
    
    async def test_webhook(
        self,
        url: str,
        event_type: WebhookEventType,
        secret: Optional[str] = None,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Test a webhook endpoint.
        """
        try:
            # Create test event data
            test_event = MediaEventData(
                event_id=uuid4(),
                event_type=event_type,
                timestamp=datetime.utcnow(),
                source="media-lifecycle-service",
                file_id=uuid4(),
                filename="test-file.jpg",
                media_type=MediaType.IMAGE,
                status=MediaStatus.READY,
                owner_id=uuid4(),
                file_size=1024,
                mime_type="image/jpeg"
            )
            
            # Create test payload
            payload = WebhookPayload(
                webhook_id=uuid4(),
                subscription_id=uuid4(),
                delivery_attempt=1,
                data=test_event,
                signature="",
                timestamp=datetime.utcnow()
            )
            
            payload_json = payload.model_dump_json()
            
            # Calculate signature if secret provided
            if secret:
                signature = self._calculate_signature(payload_json, secret)
                payload.signature = signature
                payload_json = payload.model_dump_json()
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-ID": str(payload.webhook_id),
                "X-Webhook-Timestamp": str(int(payload.timestamp.timestamp())),
                "X-Webhook-Signature": payload.signature if secret else "",
                "X-Webhook-Test": "true"
            }
            
            # Make request
            start_time = datetime.utcnow()
            
            if not self.http_client:
                await self.initialize()
            
            async with self.http_client.post(
                url,
                data=payload_json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds)
            ) as response:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                response_body = await response.text()
                
                return {
                    "success": response.status < 400,
                    "http_status_code": response.status,
                    "response_headers": dict(response.headers),
                    "response_body": response_body[:1000],
                    "request_duration": duration,
                    "test_payload": payload.model_dump()
                }
        
        except Exception as e:
            return {
                "success": False,
                "error_message": str(e),
                "request_duration": 0,
                "test_payload": payload.model_dump() if 'payload' in locals() else {}
            }