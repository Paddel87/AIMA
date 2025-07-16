#!/usr/bin/env python3
"""
Message broker connection and event publishing for the AIMA User Management Service.

This module handles RabbitMQ connections and event publishing for inter-service communication.
"""

import json
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# Global connection and channel
connection = None
channel = None
exchanges = {}
queues = {}


class EventTypes:
    """Event type constants for user management."""
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_ROLE_CHANGED = "user.role_changed"
    SESSION_CREATED = "session.created"
    SESSION_EXPIRED = "session.expired"
    AUDIT_LOG_CREATED = "audit.log_created"


async def init_messaging() -> None:
    """Initialize RabbitMQ connection and setup exchanges/queues."""
    global connection, channel, exchanges, queues
    
    settings = get_settings()
    
    try:
        # Create connection
        connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            heartbeat=600,
            blocked_connection_timeout=300,
        )
        
        # Create channel
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)
        
        # Declare exchanges
        exchanges["user_events"] = await channel.declare_exchange(
            "aima.user.events",
            ExchangeType.TOPIC,
            durable=True
        )
        
        exchanges["system_events"] = await channel.declare_exchange(
            "aima.system.events",
            ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare queues for this service
        queues["user_management_events"] = await channel.declare_queue(
            "user_management.events",
            durable=True,
            arguments={"x-message-ttl": 86400000}  # 24 hours TTL
        )
        
        # Bind queues to exchanges
        await queues["user_management_events"].bind(
            exchanges["user_events"],
            "user.*"
        )
        
        logger.info(
            "RabbitMQ connection initialized",
            exchanges=list(exchanges.keys()),
            queues=list(queues.keys())
        )
        
    except Exception as e:
        logger.error("Failed to initialize RabbitMQ connection", error=str(e))
        raise


async def close_messaging() -> None:
    """Close RabbitMQ connection."""
    global connection, channel
    
    if channel:
        await channel.close()
    
    if connection:
        await connection.close()
    
    logger.info("RabbitMQ connection closed")


class EventPublisher:
    """Publishes events to RabbitMQ exchanges."""
    
    def __init__(self):
        self.channel = channel
        self.exchanges = exchanges
    
    async def publish_user_event(
        self,
        event_type: str,
        user_id: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """Publish a user-related event."""
        await self._publish_event(
            exchange_name="user_events",
            routing_key=event_type,
            event_type=event_type,
            entity_id=user_id,
            data=data,
            correlation_id=correlation_id
        )
    
    async def publish_system_event(
        self,
        event_type: str,
        entity_id: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """Publish a system-related event."""
        await self._publish_event(
            exchange_name="system_events",
            routing_key=event_type,
            event_type=event_type,
            entity_id=entity_id,
            data=data,
            correlation_id=correlation_id
        )
    
    async def _publish_event(
        self,
        exchange_name: str,
        routing_key: str,
        event_type: str,
        entity_id: str,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> None:
        """Internal method to publish events."""
        if not self.channel or not self.exchanges:
            raise RuntimeError("Messaging not initialized")
        
        event_payload = {
            "event_type": event_type,
            "entity_id": entity_id,
            "service": "user-management",
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id,
            "data": data
        }
        
        message = Message(
            json.dumps(event_payload).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={
                "event_type": event_type,
                "service": "user-management",
                "correlation_id": correlation_id
            }
        )
        
        try:
            await self.exchanges[exchange_name].publish(
                message,
                routing_key=routing_key
            )
            
            logger.debug(
                "Event published",
                event_type=event_type,
                entity_id=entity_id,
                routing_key=routing_key,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_type=event_type,
                entity_id=entity_id,
                error=str(e)
            )
            raise


class EventConsumer:
    """Consumes events from RabbitMQ queues."""
    
    def __init__(self):
        self.channel = channel
        self.queues = queues
        self.handlers: Dict[str, Callable] = {}
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler for a specific event type."""
        self.handlers[event_type] = handler
        logger.debug("Event handler registered", event_type=event_type)
    
    async def start_consuming(self, queue_name: str = "user_management_events") -> None:
        """Start consuming messages from a queue."""
        if not self.channel or not self.queues:
            raise RuntimeError("Messaging not initialized")
        
        queue = self.queues[queue_name]
        
        async def process_message(message: aio_pika.IncomingMessage) -> None:
            async with message.process():
                try:
                    event_data = json.loads(message.body.decode())
                    event_type = event_data.get("event_type")
                    
                    if event_type in self.handlers:
                        await self.handlers[event_type](event_data)
                        logger.debug(
                            "Event processed",
                            event_type=event_type,
                            entity_id=event_data.get("entity_id")
                        )
                    else:
                        logger.warning(
                            "No handler for event type",
                            event_type=event_type
                        )
                        
                except Exception as e:
                    logger.error(
                        "Failed to process message",
                        error=str(e),
                        message_body=message.body.decode()[:200]
                    )
                    raise
        
        await queue.consume(process_message)
        logger.info("Started consuming messages", queue=queue_name)
    
    async def stop_consuming(self, queue_name: str = "user_management_events") -> None:
        """Stop consuming messages from a queue."""
        if queue_name in self.queues:
            await self.queues[queue_name].cancel()
            logger.info("Stopped consuming messages", queue=queue_name)


class UserEventHandlers:
    """Event handlers for user-related events."""
    
    @staticmethod
    async def handle_user_created(event_data: Dict[str, Any]) -> None:
        """Handle user created event."""
        logger.info(
            "User created event received",
            user_id=event_data.get("entity_id"),
            data=event_data.get("data")
        )
        # Add any additional processing logic here
    
    @staticmethod
    async def handle_user_updated(event_data: Dict[str, Any]) -> None:
        """Handle user updated event."""
        logger.info(
            "User updated event received",
            user_id=event_data.get("entity_id"),
            data=event_data.get("data")
        )
        # Add any additional processing logic here
    
    @staticmethod
    async def handle_user_deleted(event_data: Dict[str, Any]) -> None:
        """Handle user deleted event."""
        logger.info(
            "User deleted event received",
            user_id=event_data.get("entity_id"),
            data=event_data.get("data")
        )
        # Add any additional processing logic here


async def health_check() -> bool:
    """Check RabbitMQ health."""
    try:
        if not connection or connection.is_closed:
            return False
        
        if not channel or channel.is_closed:
            return False
        
        return True
    except Exception as e:
        logger.error("RabbitMQ health check failed", error=str(e))
        return False


# Global instances
event_publisher = EventPublisher()
event_consumer = EventConsumer()
user_event_handlers = UserEventHandlers()

# Register default event handlers
event_consumer.register_handler(EventTypes.USER_CREATED, user_event_handlers.handle_user_created)
event_consumer.register_handler(EventTypes.USER_UPDATED, user_event_handlers.handle_user_updated)
event_consumer.register_handler(EventTypes.USER_DELETED, user_event_handlers.handle_user_deleted)