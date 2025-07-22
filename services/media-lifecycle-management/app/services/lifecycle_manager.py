#!/usr/bin/env python3
"""
Media Lifecycle Manager for the AIMA Media Lifecycle Management Service.

This module implements the core business logic for managing media file lifecycles,
including upload processing, status transitions, cleanup, and archival.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

from ..core.database import MediaFile, MediaTag, ProcessingJob, StorageUsage
from ..core.storage import StorageManager
from ..core.redis_client import CacheManager, SessionManager
from ..models.media import (
    MediaType, MediaStatus, ProcessingOperation, StorageTier,
    MediaFileCreate, MediaFileUpdate, MediaMetadata
)
from ..models.common import ProcessingStatus, ProcessingProgress
from .media_processor import MediaProcessor
from .metadata_extractor import MetadataExtractor
from .webhook_service import WebhookService
from ..middleware.error_handling import MediaServiceException, StorageError


logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages the complete lifecycle of media files."""
    
    def __init__(
        self,
        storage_manager: StorageManager,
        cache_manager: CacheManager,
        session_manager: SessionManager,
        media_processor: MediaProcessor,
        metadata_extractor: MetadataExtractor,
        webhook_service: WebhookService
    ):
        self.storage = storage_manager
        self.cache = cache_manager
        self.sessions = session_manager
        self.processor = media_processor
        self.metadata_extractor = metadata_extractor
        self.webhooks = webhook_service
        
        # Configuration
        self.cleanup_interval = timedelta(hours=1)
        self.archive_threshold = timedelta(days=30)
        self.temp_file_ttl = timedelta(hours=24)
        self.processing_timeout = timedelta(hours=2)
    
    async def initiate_upload(
        self,
        db: AsyncSession,
        user_id: UUID,
        upload_request: MediaFileCreate,
        file_size: int,
        content_type: str
    ) -> Tuple[UUID, str, str]:
        """
        Initiate a media file upload process.
        
        Returns:
            Tuple of (file_id, upload_url, upload_id)
        """
        try:
            # Generate file ID and upload session
            file_id = uuid4()
            upload_id = f"upload_{file_id}_{int(datetime.utcnow().timestamp())}"
            
            # Determine media type
            media_type = self._determine_media_type(content_type)
            
            # Generate storage path
            storage_path = self.storage.generate_storage_path(
                user_id=user_id,
                filename=upload_request.filename,
                media_type=media_type.value
            )
            
            # Create database record
            media_file = MediaFile(
                id=file_id,
                filename=upload_request.filename,
                title=upload_request.title,
                description=upload_request.description,
                file_size=file_size,
                mime_type=content_type,
                media_type=media_type,
                status=MediaStatus.UPLOADING,
                storage_path=storage_path,
                storage_tier=upload_request.storage_tier,
                storage_bucket=self.storage.bucket_name,
                is_public=upload_request.is_public,
                owner_id=user_id,
                expires_at=upload_request.expires_at,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(media_file)
            
            # Add tags if provided
            if upload_request.tags:
                for tag_data in upload_request.tags:
                    tag = MediaTag(
                        id=uuid4(),
                        file_id=file_id,
                        name=tag_data.name,
                        value=tag_data.value,
                        category=tag_data.category,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(tag)
            
            await db.commit()
            
            # Generate pre-signed upload URL
            upload_url = await self.storage.generate_presigned_upload_url(
                storage_path,
                content_type,
                file_size,
                expires_in=3600  # 1 hour
            )
            
            # Cache upload session
            await self.cache.set(
                f"upload_session:{upload_id}",
                {
                    "file_id": str(file_id),
                    "user_id": str(user_id),
                    "storage_path": storage_path,
                    "expected_size": file_size,
                    "content_type": content_type,
                    "created_at": datetime.utcnow().isoformat()
                },
                ttl=3600
            )
            
            logger.info(f"Upload initiated for file {file_id} by user {user_id}")
            
            return file_id, upload_url, upload_id
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to initiate upload: {e}")
            raise MediaServiceException(f"Upload initiation failed: {str(e)}")
    
    async def complete_upload(
        self,
        db: AsyncSession,
        upload_id: str,
        checksum: Optional[str] = None
    ) -> UUID:
        """
        Complete the upload process and start post-upload processing.
        
        Returns:
            File ID of the uploaded file
        """
        try:
            # Get upload session
            session_data = await self.cache.get(f"upload_session:{upload_id}")
            if not session_data:
                raise MediaServiceException("Upload session not found or expired")
            
            file_id = UUID(session_data["file_id"])
            storage_path = session_data["storage_path"]
            expected_size = session_data["expected_size"]
            
            # Verify file exists in storage
            if not await self.storage.file_exists(storage_path):
                raise StorageError("Uploaded file not found in storage")
            
            # Get actual file metadata
            file_metadata = await self.storage.get_file_metadata(storage_path)
            actual_size = file_metadata.get("size", 0)
            
            # Verify file size
            if actual_size != expected_size:
                logger.warning(
                    f"File size mismatch for {file_id}: expected {expected_size}, got {actual_size}"
                )
            
            # Calculate checksum if not provided
            if not checksum:
                checksum = await self.storage.calculate_file_hash(storage_path)
            
            # Update database record
            stmt = (
                update(MediaFile)
                .where(MediaFile.id == file_id)
                .values(
                    status=MediaStatus.PROCESSING,
                    file_size=actual_size,
                    checksum=checksum,
                    updated_at=datetime.utcnow()
                )
            )
            await db.execute(stmt)
            await db.commit()
            
            # Clean up upload session
            await self.cache.delete(f"upload_session:{upload_id}")
            
            # Start post-upload processing
            await self._start_post_upload_processing(db, file_id)
            
            # Send webhook notification
            await self.webhooks.send_media_uploaded_event(
                file_id=file_id,
                user_id=UUID(session_data["user_id"]),
                filename=session_data.get("filename", "unknown"),
                file_size=actual_size
            )
            
            logger.info(f"Upload completed for file {file_id}")
            
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to complete upload {upload_id}: {e}")
            raise MediaServiceException(f"Upload completion failed: {str(e)}")
    
    async def _start_post_upload_processing(
        self,
        db: AsyncSession,
        file_id: UUID
    ) -> None:
        """
        Start post-upload processing tasks.
        """
        try:
            # Get media file
            result = await db.execute(
                select(MediaFile).where(MediaFile.id == file_id)
            )
            media_file = result.scalar_one_or_none()
            
            if not media_file:
                raise MediaServiceException(f"Media file {file_id} not found")
            
            # Extract metadata
            metadata_job_id = await self._create_processing_job(
                db,
                file_id,
                ProcessingOperation.METADATA_EXTRACTION,
                priority=1  # High priority for metadata
            )
            
            # Generate thumbnail for images and videos
            if media_file.media_type in [MediaType.IMAGE, MediaType.VIDEO]:
                thumbnail_job_id = await self._create_processing_job(
                    db,
                    file_id,
                    ProcessingOperation.THUMBNAIL,
                    parameters={"width": 300, "height": 300, "quality": 85},
                    priority=2
                )
            
            # Schedule background processing
            asyncio.create_task(self._process_jobs_for_file(file_id))
            
        except Exception as e:
            logger.error(f"Failed to start post-upload processing for {file_id}: {e}")
            # Don't raise here to avoid failing the upload completion
    
    async def _create_processing_job(
        self,
        db: AsyncSession,
        file_id: UUID,
        operation: ProcessingOperation,
        parameters: Optional[Dict[str, Any]] = None,
        priority: int = 5
    ) -> UUID:
        """
        Create a processing job.
        """
        job_id = uuid4()
        
        job = ProcessingJob(
            id=job_id,
            file_id=file_id,
            operation=operation,
            status=ProcessingStatus.PENDING,
            parameters=parameters or {},
            priority=priority,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(job)
        await db.commit()
        
        logger.info(f"Created processing job {job_id} for file {file_id}")
        
        return job_id
    
    async def _process_jobs_for_file(self, file_id: UUID) -> None:
        """
        Process all pending jobs for a file.
        """
        try:
            # This would typically be handled by a background worker
            # For now, we'll process jobs sequentially
            
            from ..core.database import get_db
            
            async for db in get_db():
                # Get pending jobs
                result = await db.execute(
                    select(ProcessingJob)
                    .where(
                        and_(
                            ProcessingJob.file_id == file_id,
                            ProcessingJob.status == ProcessingStatus.PENDING
                        )
                    )
                    .order_by(ProcessingJob.priority, ProcessingJob.created_at)
                )
                jobs = result.scalars().all()
                
                for job in jobs:
                    await self._execute_processing_job(db, job)
                
                break  # Exit the async generator
                
        except Exception as e:
            logger.error(f"Failed to process jobs for file {file_id}: {e}")
    
    async def _execute_processing_job(
        self,
        db: AsyncSession,
        job: ProcessingJob
    ) -> None:
        """
        Execute a single processing job.
        """
        try:
            # Update job status to running
            job.status = ProcessingStatus.RUNNING
            job.started_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            await db.commit()
            
            # Send webhook notification
            await self.webhooks.send_job_started_event(job.id, job.file_id, job.operation)
            
            # Execute the operation
            if job.operation == ProcessingOperation.METADATA_EXTRACTION:
                await self._extract_metadata(db, job)
            elif job.operation == ProcessingOperation.THUMBNAIL:
                await self._generate_thumbnail(db, job)
            elif job.operation == ProcessingOperation.TRANSCODE:
                await self._transcode_media(db, job)
            else:
                raise MediaServiceException(f"Unknown operation: {job.operation}")
            
            # Update job status to completed
            job.status = ProcessingStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            
            if job.started_at:
                job.processing_time = (job.completed_at - job.started_at).total_seconds()
            
            await db.commit()
            
            # Send webhook notification
            await self.webhooks.send_job_completed_event(job.id, job.file_id, job.operation)
            
            logger.info(f"Completed processing job {job.id}")
            
        except Exception as e:
            # Update job status to failed
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            
            if job.started_at:
                job.processing_time = (job.completed_at - job.started_at).total_seconds()
            
            await db.commit()
            
            # Send webhook notification
            await self.webhooks.send_job_failed_event(job.id, job.file_id, job.operation, str(e))
            
            logger.error(f"Failed processing job {job.id}: {e}")
    
    async def _extract_metadata(
        self,
        db: AsyncSession,
        job: ProcessingJob
    ) -> None:
        """
        Extract metadata from a media file.
        """
        # Get media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == job.file_id)
        )
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise MediaServiceException(f"Media file {job.file_id} not found")
        
        # Download file temporarily for processing
        temp_path = f"/tmp/{job.file_id}_{media_file.filename}"
        
        try:
            # Download file
            await self.storage.download_file(media_file.storage_path, temp_path)
            
            # Extract metadata
            metadata = await self.metadata_extractor.extract_metadata(
                temp_path,
                media_file.media_type
            )
            
            # Update media file with metadata
            media_file.metadata = metadata
            media_file.updated_at = datetime.utcnow()
            
            # If this is the first processing, update status to ready
            if media_file.status == MediaStatus.PROCESSING:
                media_file.status = MediaStatus.READY
            
            await db.commit()
            
        finally:
            # Clean up temporary file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    async def _generate_thumbnail(
        self,
        db: AsyncSession,
        job: ProcessingJob
    ) -> None:
        """
        Generate thumbnail for a media file.
        """
        # Get media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == job.file_id)
        )
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise MediaServiceException(f"Media file {job.file_id} not found")
        
        # Generate thumbnail using media processor
        thumbnail_path = await self.processor.generate_thumbnail(
            media_file.storage_path,
            job.parameters.get("width", 300),
            job.parameters.get("height", 300),
            quality=job.parameters.get("quality", 85)
        )
        
        # Store thumbnail URL in job result
        job.result_url = thumbnail_path
    
    async def _transcode_media(
        self,
        db: AsyncSession,
        job: ProcessingJob
    ) -> None:
        """
        Transcode a media file.
        """
        # Get media file
        result = await db.execute(
            select(MediaFile).where(MediaFile.id == job.file_id)
        )
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise MediaServiceException(f"Media file {job.file_id} not found")
        
        # Transcode using media processor
        result_path = await self.processor.transcode_video(
            media_file.storage_path,
            job.parameters.get("format", "mp4"),
            job.parameters.get("quality", "medium")
        )
        
        # Store result URL in job
        job.result_url = result_path
    
    async def update_media_file(
        self,
        db: AsyncSession,
        file_id: UUID,
        user_id: UUID,
        update_data: MediaFileUpdate
    ) -> MediaFile:
        """
        Update a media file.
        """
        try:
            # Get media file
            result = await db.execute(
                select(MediaFile)
                .where(
                    and_(
                        MediaFile.id == file_id,
                        MediaFile.owner_id == user_id
                    )
                )
            )
            media_file = result.scalar_one_or_none()
            
            if not media_file:
                raise MediaServiceException("Media file not found or access denied")
            
            # Update fields
            update_dict = update_data.model_dump(exclude_unset=True)
            
            for field, value in update_dict.items():
                if hasattr(media_file, field):
                    setattr(media_file, field, value)
            
            media_file.updated_at = datetime.utcnow()
            
            await db.commit()
            
            # Invalidate cache
            await self.cache.delete(f"media_file:{file_id}")
            
            logger.info(f"Updated media file {file_id}")
            
            return media_file
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to update media file {file_id}: {e}")
            raise MediaServiceException(f"Update failed: {str(e)}")
    
    async def delete_media_file(
        self,
        db: AsyncSession,
        file_id: UUID,
        user_id: UUID,
        permanent: bool = False
    ) -> bool:
        """
        Delete a media file (soft delete by default).
        """
        try:
            # Get media file
            result = await db.execute(
                select(MediaFile)
                .where(
                    and_(
                        MediaFile.id == file_id,
                        MediaFile.owner_id == user_id
                    )
                )
            )
            media_file = result.scalar_one_or_none()
            
            if not media_file:
                raise MediaServiceException("Media file not found or access denied")
            
            if permanent:
                # Delete from storage
                await self.storage.delete_file(media_file.storage_path)
                
                # Delete from database
                await db.delete(media_file)
            else:
                # Soft delete
                media_file.status = MediaStatus.DELETED
                media_file.updated_at = datetime.utcnow()
            
            await db.commit()
            
            # Invalidate cache
            await self.cache.delete(f"media_file:{file_id}")
            
            # Send webhook notification
            await self.webhooks.send_media_deleted_event(
                file_id=file_id,
                user_id=user_id,
                permanent=permanent
            )
            
            logger.info(f"Deleted media file {file_id} (permanent: {permanent})")
            
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to delete media file {file_id}: {e}")
            raise MediaServiceException(f"Deletion failed: {str(e)}")
    
    async def cleanup_expired_files(self, db: AsyncSession) -> int:
        """
        Clean up expired files.
        
        Returns:
            Number of files cleaned up
        """
        try:
            now = datetime.utcnow()
            
            # Find expired files
            result = await db.execute(
                select(MediaFile)
                .where(
                    and_(
                        MediaFile.expires_at.isnot(None),
                        MediaFile.expires_at <= now,
                        MediaFile.status != MediaStatus.DELETED
                    )
                )
            )
            expired_files = result.scalars().all()
            
            cleaned_count = 0
            
            for media_file in expired_files:
                try:
                    # Delete from storage
                    await self.storage.delete_file(media_file.storage_path)
                    
                    # Update status
                    media_file.status = MediaStatus.DELETED
                    media_file.updated_at = now
                    
                    # Send webhook notification
                    await self.webhooks.send_media_expired_event(
                        file_id=media_file.id,
                        user_id=media_file.owner_id
                    )
                    
                    cleaned_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to clean up expired file {media_file.id}: {e}")
            
            await db.commit()
            
            logger.info(f"Cleaned up {cleaned_count} expired files")
            
            return cleaned_count
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to cleanup expired files: {e}")
            return 0
    
    async def archive_old_files(
        self,
        db: AsyncSession,
        threshold_days: int = 30
    ) -> int:
        """
        Archive old files to cold storage.
        
        Returns:
            Number of files archived
        """
        try:
            threshold_date = datetime.utcnow() - timedelta(days=threshold_days)
            
            # Find old files in hot/warm storage
            result = await db.execute(
                select(MediaFile)
                .where(
                    and_(
                        MediaFile.last_accessed <= threshold_date,
                        MediaFile.storage_tier.in_([StorageTier.HOT, StorageTier.WARM]),
                        MediaFile.status == MediaStatus.READY
                    )
                )
            )
            old_files = result.scalars().all()
            
            archived_count = 0
            
            for media_file in old_files:
                try:
                    # Move to archive tier
                    await self._change_storage_tier(
                        media_file,
                        StorageTier.ARCHIVE
                    )
                    
                    media_file.storage_tier = StorageTier.ARCHIVE
                    media_file.updated_at = datetime.utcnow()
                    
                    # Send webhook notification
                    await self.webhooks.send_media_archived_event(
                        file_id=media_file.id,
                        user_id=media_file.owner_id
                    )
                    
                    archived_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to archive file {media_file.id}: {e}")
            
            await db.commit()
            
            logger.info(f"Archived {archived_count} old files")
            
            return archived_count
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to archive old files: {e}")
            return 0
    
    async def _change_storage_tier(
        self,
        media_file: MediaFile,
        new_tier: StorageTier
    ) -> None:
        """
        Change the storage tier of a media file.
        """
        # This would involve moving the file to different storage classes
        # For now, we'll just update the metadata
        pass
    
    def _determine_media_type(self, content_type: str) -> MediaType:
        """
        Determine media type from content type.
        """
        if content_type.startswith("image/"):
            return MediaType.IMAGE
        elif content_type.startswith("video/"):
            return MediaType.VIDEO
        elif content_type.startswith("audio/"):
            return MediaType.AUDIO
        elif content_type in [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain"
        ]:
            return MediaType.DOCUMENT
        else:
            return MediaType.OTHER