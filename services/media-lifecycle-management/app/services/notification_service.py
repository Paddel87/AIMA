#!/usr/bin/env python3
"""
Notification Service for the AIMA Media Lifecycle Management Service.

This module provides notification capabilities including email, SMS, and push notifications
for various media lifecycle events.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
import json
import aiohttp
import asyncio
from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path

from ..core.config import get_settings
from ..core.redis_client import CacheManager
from ..models.common import NotificationChannel, NotificationPriority, NotificationStatus
from ..models.media import MediaFile, ProcessingJob
from ..middleware.error_handling import MediaServiceException


logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationTemplate:
    """Notification template management."""
    
    def __init__(self, template_dir: str = "templates/notifications"):
        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a notification template with context."""
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            return self._get_fallback_template(template_name, context)
    
    def _get_fallback_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Get fallback template content."""
        fallback_templates = {
            "upload_complete.html": """
            <h2>Upload Complete</h2>
            <p>Your file "{{ filename }}" has been successfully uploaded.</p>
            <p>File ID: {{ file_id }}</p>
            <p>Upload time: {{ upload_time }}</p>
            """,
            "processing_complete.html": """
            <h2>Processing Complete</h2>
            <p>Processing of "{{ filename }}" has been completed.</p>
            <p>Operation: {{ operation }}</p>
            <p>Status: {{ status }}</p>
            """,
            "processing_failed.html": """
            <h2>Processing Failed</h2>
            <p>Processing of "{{ filename }}" has failed.</p>
            <p>Operation: {{ operation }}</p>
            <p>Error: {{ error_message }}</p>
            """,
            "storage_quota_warning.html": """
            <h2>Storage Quota Warning</h2>
            <p>Your storage usage is at {{ usage_percentage }}% of your quota.</p>
            <p>Used: {{ used_storage }} / {{ total_quota }}</p>
            """
        }
        
        template_content = fallback_templates.get(template_name, "Notification: {{ message }}")
        template = Template(template_content)
        return template.render(**context)


class EmailNotificationService:
    """Email notification service."""
    
    def __init__(self, template_manager: NotificationTemplate):
        self.template_manager = template_manager
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_use_tls = settings.SMTP_USE_TLS
        self.from_email = settings.FROM_EMAIL
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send an email notification."""
        try:
            # Render email content
            html_content = self.template_manager.render_template(template_name, context)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    self._add_attachment(msg, attachment)
            
            # Send email
            await self._send_smtp_email(msg, to_email)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message."""
        try:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment['content'])
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment["filename"]}'
            )
            msg.attach(part)
        except Exception as e:
            logger.error(f"Failed to add attachment {attachment.get('filename', 'unknown')}: {e}")
    
    async def _send_smtp_email(self, msg: MIMEMultipart, to_email: str):
        """Send email via SMTP."""
        loop = asyncio.get_event_loop()
        
        def _send():
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg, to_addrs=[to_email])
        
        await loop.run_in_executor(None, _send)


class SMSNotificationService:
    """SMS notification service."""
    
    def __init__(self):
        self.sms_api_url = settings.SMS_API_URL
        self.sms_api_key = settings.SMS_API_KEY
        self.sms_from_number = settings.SMS_FROM_NUMBER
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send an SMS notification."""
        try:
            if not self.sms_api_url or not self.sms_api_key:
                logger.warning("SMS service not configured")
                return False
            
            payload = {
                "to": to_number,
                "from": self.sms_from_number,
                "message": message,
                "priority": priority.value
            }
            
            headers = {
                "Authorization": f"Bearer {self.sms_api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.sms_api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        logger.info(f"SMS sent successfully to {to_number}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send SMS to {to_number}: {response.status} - {error_text}")
                        return False
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            return False


class PushNotificationService:
    """Push notification service."""
    
    def __init__(self):
        self.fcm_server_key = settings.FCM_SERVER_KEY
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.apns_key_id = settings.APNS_KEY_ID
        self.apns_team_id = settings.APNS_TEAM_ID
        self.apns_bundle_id = settings.APNS_BUNDLE_ID
    
    async def send_push_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        platform: str = "android"
    ) -> bool:
        """Send a push notification."""
        try:
            if platform.lower() == "android":
                return await self._send_fcm_notification(device_token, title, body, data)
            elif platform.lower() == "ios":
                return await self._send_apns_notification(device_token, title, body, data)
            else:
                logger.error(f"Unsupported push notification platform: {platform}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send push notification to {device_token}: {e}")
            return False
    
    async def _send_fcm_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send FCM (Firebase Cloud Messaging) notification."""
        if not self.fcm_server_key:
            logger.warning("FCM server key not configured")
            return False
        
        payload = {
            "to": device_token,
            "notification": {
                "title": title,
                "body": body
            }
        }
        
        if data:
            payload["data"] = data
        
        headers = {
            "Authorization": f"key={self.fcm_server_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.fcm_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success", 0) > 0:
                        logger.info(f"FCM notification sent successfully to {device_token}")
                        return True
                    else:
                        logger.error(f"FCM notification failed: {result}")
                        return False
                else:
                    error_text = await response.text()
                    logger.error(f"FCM API error: {response.status} - {error_text}")
                    return False
    
    async def _send_apns_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send APNS (Apple Push Notification Service) notification."""
        # This is a simplified implementation
        # In production, you would use a proper APNS library like aioapns
        logger.warning("APNS implementation not complete - use aioapns library")
        return False


class NotificationService:
    """Main notification service that coordinates all notification channels."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.template_manager = NotificationTemplate()
        self.email_service = EmailNotificationService(self.template_manager)
        self.sms_service = SMSNotificationService()
        self.push_service = PushNotificationService()
        
        # Notification preferences cache TTL (1 hour)
        self.preferences_cache_ttl = 3600
    
    async def send_notification(
        self,
        user_id: UUID,
        notification_type: str,
        context: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, bool]:
        """Send notification through specified channels."""
        try:
            # Get user notification preferences
            preferences = await self._get_user_preferences(user_id)
            
            # Determine channels to use
            if channels is None:
                channels = self._get_default_channels(notification_type, priority)
            
            # Filter channels based on user preferences
            enabled_channels = self._filter_channels_by_preferences(channels, preferences, notification_type)
            
            # Send notifications
            results = {}
            for channel in enabled_channels:
                if channel == NotificationChannel.EMAIL:
                    results["email"] = await self._send_email_notification(
                        user_id, notification_type, context, priority
                    )
                elif channel == NotificationChannel.SMS:
                    results["sms"] = await self._send_sms_notification(
                        user_id, notification_type, context, priority
                    )
                elif channel == NotificationChannel.PUSH:
                    results["push"] = await self._send_push_notification(
                        user_id, notification_type, context, priority
                    )
            
            # Log notification attempt
            await self._log_notification(
                user_id, notification_type, enabled_channels, results, context
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")
            return {}
    
    async def _get_user_preferences(self, user_id: UUID) -> Dict[str, Any]:
        """Get user notification preferences."""
        cache_key = f"notification_preferences:{user_id}"
        
        # Try cache first
        preferences = await self.cache.get(cache_key)
        if preferences:
            return preferences
        
        # In a real implementation, this would fetch from the user service
        # For now, return default preferences
        default_preferences = {
            "email": {
                "enabled": True,
                "types": ["upload_complete", "processing_complete", "processing_failed", "storage_quota_warning"]
            },
            "sms": {
                "enabled": False,
                "types": ["processing_failed", "storage_quota_warning"]
            },
            "push": {
                "enabled": True,
                "types": ["upload_complete", "processing_complete"]
            }
        }
        
        # Cache the preferences
        await self.cache.set(cache_key, default_preferences, ttl=self.preferences_cache_ttl)
        
        return default_preferences
    
    def _get_default_channels(
        self,
        notification_type: str,
        priority: NotificationPriority
    ) -> List[NotificationChannel]:
        """Get default notification channels based on type and priority."""
        if priority == NotificationPriority.HIGH:
            return [NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH]
        elif priority == NotificationPriority.NORMAL:
            return [NotificationChannel.EMAIL, NotificationChannel.PUSH]
        else:
            return [NotificationChannel.EMAIL]
    
    def _filter_channels_by_preferences(
        self,
        channels: List[NotificationChannel],
        preferences: Dict[str, Any],
        notification_type: str
    ) -> List[NotificationChannel]:
        """Filter channels based on user preferences."""
        enabled_channels = []
        
        for channel in channels:
            channel_name = channel.value.lower()
            channel_prefs = preferences.get(channel_name, {})
            
            if (channel_prefs.get("enabled", False) and 
                notification_type in channel_prefs.get("types", [])):
                enabled_channels.append(channel)
        
        return enabled_channels
    
    async def _send_email_notification(
        self,
        user_id: UUID,
        notification_type: str,
        context: Dict[str, Any],
        priority: NotificationPriority
    ) -> bool:
        """Send email notification."""
        try:
            # Get user email (in real implementation, fetch from user service)
            user_email = await self._get_user_email(user_id)
            if not user_email:
                return False
            
            # Get email template and subject
            template_name = f"{notification_type}.html"
            subject = self._get_email_subject(notification_type, context)
            
            return await self.email_service.send_email(
                to_email=user_email,
                subject=subject,
                template_name=template_name,
                context=context
            )
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    async def _send_sms_notification(
        self,
        user_id: UUID,
        notification_type: str,
        context: Dict[str, Any],
        priority: NotificationPriority
    ) -> bool:
        """Send SMS notification."""
        try:
            # Get user phone number (in real implementation, fetch from user service)
            user_phone = await self._get_user_phone(user_id)
            if not user_phone:
                return False
            
            # Create SMS message
            message = self._create_sms_message(notification_type, context)
            
            return await self.sms_service.send_sms(
                to_number=user_phone,
                message=message,
                priority=priority
            )
            
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return False
    
    async def _send_push_notification(
        self,
        user_id: UUID,
        notification_type: str,
        context: Dict[str, Any],
        priority: NotificationPriority
    ) -> bool:
        """Send push notification."""
        try:
            # Get user device tokens (in real implementation, fetch from user service)
            device_tokens = await self._get_user_device_tokens(user_id)
            if not device_tokens:
                return False
            
            # Create push notification content
            title, body = self._create_push_content(notification_type, context)
            
            # Send to all user devices
            results = []
            for token_info in device_tokens:
                result = await self.push_service.send_push_notification(
                    device_token=token_info["token"],
                    title=title,
                    body=body,
                    data=context,
                    platform=token_info.get("platform", "android")
                )
                results.append(result)
            
            return any(results)  # Return True if at least one succeeded
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False
    
    async def _get_user_email(self, user_id: UUID) -> Optional[str]:
        """Get user email address."""
        # In real implementation, this would call the user service
        # For now, return a placeholder
        return f"user_{user_id}@example.com"
    
    async def _get_user_phone(self, user_id: UUID) -> Optional[str]:
        """Get user phone number."""
        # In real implementation, this would call the user service
        return None  # Not implemented
    
    async def _get_user_device_tokens(self, user_id: UUID) -> List[Dict[str, str]]:
        """Get user device tokens for push notifications."""
        # In real implementation, this would call the user service
        return []  # Not implemented
    
    def _get_email_subject(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get email subject based on notification type."""
        subjects = {
            "upload_complete": "Upload Complete - {filename}",
            "processing_complete": "Processing Complete - {filename}",
            "processing_failed": "Processing Failed - {filename}",
            "storage_quota_warning": "Storage Quota Warning",
            "media_deleted": "Media Deleted - {filename}",
            "media_archived": "Media Archived - {filename}"
        }
        
        subject_template = subjects.get(notification_type, "Notification")
        try:
            return subject_template.format(**context)
        except KeyError:
            return subject_template
    
    def _create_sms_message(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Create SMS message content."""
        messages = {
            "upload_complete": "Your file '{filename}' has been uploaded successfully.",
            "processing_complete": "Processing of '{filename}' is complete.",
            "processing_failed": "Processing of '{filename}' failed: {error_message}",
            "storage_quota_warning": "Storage quota warning: {usage_percentage}% used."
        }
        
        message_template = messages.get(notification_type, "Notification: {message}")
        try:
            return message_template.format(**context)
        except KeyError:
            return f"Notification: {notification_type}"
    
    def _create_push_content(self, notification_type: str, context: Dict[str, Any]) -> Tuple[str, str]:
        """Create push notification title and body."""
        content = {
            "upload_complete": (
                "Upload Complete",
                "Your file '{filename}' has been uploaded successfully."
            ),
            "processing_complete": (
                "Processing Complete",
                "Processing of '{filename}' is complete."
            ),
            "processing_failed": (
                "Processing Failed",
                "Processing of '{filename}' failed."
            ),
            "storage_quota_warning": (
                "Storage Warning",
                "You're using {usage_percentage}% of your storage quota."
            )
        }
        
        title_template, body_template = content.get(
            notification_type,
            ("Notification", "You have a new notification.")
        )
        
        try:
            title = title_template.format(**context)
            body = body_template.format(**context)
        except KeyError:
            title = title_template
            body = body_template
        
        return title, body
    
    async def _log_notification(
        self,
        user_id: UUID,
        notification_type: str,
        channels: List[NotificationChannel],
        results: Dict[str, bool],
        context: Dict[str, Any]
    ):
        """Log notification attempt."""
        log_entry = {
            "user_id": str(user_id),
            "notification_type": notification_type,
            "channels": [channel.value for channel in channels],
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
            "context_keys": list(context.keys())  # Don't log full context for privacy
        }
        
        # Store in cache for recent notification history
        cache_key = f"notification_log:{user_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        
        try:
            # Get existing logs for today
            existing_logs = await self.cache.get(cache_key) or []
            existing_logs.append(log_entry)
            
            # Keep only last 100 notifications per day
            if len(existing_logs) > 100:
                existing_logs = existing_logs[-100:]
            
            # Store back to cache (TTL: 7 days)
            await self.cache.set(cache_key, existing_logs, ttl=7 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")
    
    # Convenience methods for common notifications
    
    async def notify_upload_complete(
        self,
        user_id: UUID,
        media_file: MediaFile,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, bool]:
        """Send upload complete notification."""
        context = {
            "filename": media_file.filename,
            "file_id": str(media_file.id),
            "upload_time": media_file.created_at.isoformat(),
            "file_size": media_file.file_size,
            "media_type": media_file.media_type.value
        }
        
        return await self.send_notification(
            user_id=user_id,
            notification_type="upload_complete",
            context=context,
            priority=priority
        )
    
    async def notify_processing_complete(
        self,
        user_id: UUID,
        media_file: MediaFile,
        processing_job: ProcessingJob,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, bool]:
        """Send processing complete notification."""
        context = {
            "filename": media_file.filename,
            "file_id": str(media_file.id),
            "operation": processing_job.operation.value,
            "status": processing_job.status.value,
            "processing_time": processing_job.processing_time or 0
        }
        
        return await self.send_notification(
            user_id=user_id,
            notification_type="processing_complete",
            context=context,
            priority=priority
        )
    
    async def notify_processing_failed(
        self,
        user_id: UUID,
        media_file: MediaFile,
        processing_job: ProcessingJob,
        error_message: str,
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> Dict[str, bool]:
        """Send processing failed notification."""
        context = {
            "filename": media_file.filename,
            "file_id": str(media_file.id),
            "operation": processing_job.operation.value,
            "error_message": error_message
        }
        
        return await self.send_notification(
            user_id=user_id,
            notification_type="processing_failed",
            context=context,
            priority=priority
        )
    
    async def notify_storage_quota_warning(
        self,
        user_id: UUID,
        usage_percentage: float,
        used_storage: int,
        total_quota: int,
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> Dict[str, bool]:
        """Send storage quota warning notification."""
        context = {
            "usage_percentage": usage_percentage,
            "used_storage": used_storage,
            "total_quota": total_quota,
            "used_storage_gb": used_storage / (1024**3),
            "total_quota_gb": total_quota / (1024**3)
        }
        
        return await self.send_notification(
            user_id=user_id,
            notification_type="storage_quota_warning",
            context=context,
            priority=priority
        )