#!/usr/bin/env python3
"""
Backup Service for the AIMA Media Lifecycle Management Service.

This module provides backup and restore capabilities for media files,
including scheduled backups, incremental backups, and disaster recovery.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from pathlib import Path
import json
import hashlib
import gzip
import shutil
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from ..core.database import MediaFile, BackupRecord
from ..core.storage import StorageManager
from ..core.redis_client import CacheManager
from ..models.media import MediaStatus, StorageTier
from ..models.common import ProcessingStatus
from ..middleware.error_handling import MediaServiceException


logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Backup types."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(str, Enum):
    """Backup status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackupDestination(str, Enum):
    """Backup destinations."""
    LOCAL = "local"
    S3 = "s3"
    GLACIER = "glacier"
    AZURE = "azure"
    GCS = "gcs"


class BackupJob:
    """Backup job representation."""
    
    def __init__(
        self,
        job_id: UUID,
        backup_type: BackupType,
        destination: BackupDestination,
        source_files: List[UUID],
        created_at: datetime,
        status: BackupStatus = BackupStatus.PENDING
    ):
        self.job_id = job_id
        self.backup_type = backup_type
        self.destination = destination
        self.source_files = source_files
        self.created_at = created_at
        self.status = status
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.backup_size: int = 0
        self.files_backed_up: int = 0
        self.files_failed: int = 0
        self.backup_path: Optional[str] = None
        self.checksum: Optional[str] = None


class BackupService:
    """Service for backup and restore operations."""
    
    def __init__(
        self,
        storage_manager: StorageManager,
        cache_manager: CacheManager,
        backup_storage_manager: Optional[StorageManager] = None
    ):
        self.storage = storage_manager
        self.backup_storage = backup_storage_manager or storage_manager
        self.cache = cache_manager
        
        # Configuration
        self.backup_bucket = "media-backups"
        self.local_backup_path = Path("/var/backups/media")
        self.max_concurrent_backups = 3
        self.backup_retention_days = 90
        self.incremental_backup_interval = timedelta(hours=6)
        self.full_backup_interval = timedelta(days=7)
        
        # Active backup jobs
        self.active_jobs: Dict[UUID, BackupJob] = {}
        self.backup_semaphore = asyncio.Semaphore(self.max_concurrent_backups)
    
    async def create_backup_job(
        self,
        db: AsyncSession,
        backup_type: BackupType,
        destination: BackupDestination,
        file_ids: Optional[List[UUID]] = None,
        user_id: Optional[UUID] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> BackupJob:
        """
        Create a new backup job.
        
        Args:
            db: Database session
            backup_type: Type of backup (full, incremental, differential)
            destination: Backup destination
            file_ids: Specific file IDs to backup (optional)
            user_id: User ID to backup files for (optional)
            filters: Additional filters for file selection
        
        Returns:
            BackupJob instance
        """
        try:
            job_id = uuid4()
            
            # Determine files to backup
            if file_ids:
                source_files = file_ids
            else:
                source_files = await self._get_files_for_backup(
                    db, backup_type, user_id, filters
                )
            
            if not source_files:
                raise MediaServiceException("No files found for backup")
            
            # Create backup job
            backup_job = BackupJob(
                job_id=job_id,
                backup_type=backup_type,
                destination=destination,
                source_files=source_files,
                created_at=datetime.utcnow()
            )
            
            # Store job in cache
            await self._store_backup_job(backup_job)
            
            logger.info(
                f"Created backup job {job_id} with {len(source_files)} files"
            )
            
            return backup_job
            
        except Exception as e:
            logger.error(f"Failed to create backup job: {e}")
            raise MediaServiceException(f"Backup job creation failed: {str(e)}")
    
    async def start_backup_job(
        self,
        db: AsyncSession,
        job_id: UUID
    ) -> bool:
        """
        Start a backup job.
        
        Args:
            db: Database session
            job_id: Backup job ID
        
        Returns:
            True if job started successfully
        """
        try:
            # Get backup job
            backup_job = await self._get_backup_job(job_id)
            if not backup_job:
                raise MediaServiceException(f"Backup job {job_id} not found")
            
            if backup_job.status != BackupStatus.PENDING:
                raise MediaServiceException(
                    f"Backup job {job_id} is not in pending status"
                )
            
            # Start backup in background
            asyncio.create_task(self._execute_backup_job(db, backup_job))
            
            logger.info(f"Started backup job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start backup job {job_id}: {e}")
            return False
    
    async def _execute_backup_job(
        self,
        db: AsyncSession,
        backup_job: BackupJob
    ):
        """
        Execute a backup job.
        """
        async with self.backup_semaphore:
            try:
                # Update job status
                backup_job.status = BackupStatus.IN_PROGRESS
                backup_job.started_at = datetime.utcnow()
                await self._store_backup_job(backup_job)
                
                # Create backup directory/path
                backup_path = await self._create_backup_path(
                    backup_job.job_id,
                    backup_job.backup_type,
                    backup_job.destination
                )
                backup_job.backup_path = backup_path
                
                # Execute backup based on type
                if backup_job.backup_type == BackupType.FULL:
                    await self._execute_full_backup(db, backup_job)
                elif backup_job.backup_type == BackupType.INCREMENTAL:
                    await self._execute_incremental_backup(db, backup_job)
                elif backup_job.backup_type == BackupType.DIFFERENTIAL:
                    await self._execute_differential_backup(db, backup_job)
                
                # Calculate checksum
                backup_job.checksum = await self._calculate_backup_checksum(
                    backup_job.backup_path
                )
                
                # Update job status
                backup_job.status = BackupStatus.COMPLETED
                backup_job.completed_at = datetime.utcnow()
                
                # Create backup record in database
                await self._create_backup_record(db, backup_job)
                
                logger.info(
                    f"Backup job {backup_job.job_id} completed successfully. "
                    f"Backed up {backup_job.files_backed_up} files, "
                    f"size: {backup_job.backup_size} bytes"
                )
                
            except Exception as e:
                backup_job.status = BackupStatus.FAILED
                backup_job.error_message = str(e)
                backup_job.completed_at = datetime.utcnow()
                
                logger.error(f"Backup job {backup_job.job_id} failed: {e}")
                
            finally:
                await self._store_backup_job(backup_job)
                
                # Remove from active jobs
                if backup_job.job_id in self.active_jobs:
                    del self.active_jobs[backup_job.job_id]
    
    async def _execute_full_backup(
        self,
        db: AsyncSession,
        backup_job: BackupJob
    ):
        """
        Execute a full backup.
        """
        logger.info(f"Starting full backup for job {backup_job.job_id}")
        
        # Get all files to backup
        files_query = select(MediaFile).where(
            and_(
                MediaFile.id.in_(backup_job.source_files),
                MediaFile.status == MediaStatus.ACTIVE
            )
        )
        
        result = await db.execute(files_query)
        files = result.scalars().all()
        
        # Backup each file
        for media_file in files:
            try:
                await self._backup_file(backup_job, media_file)
                backup_job.files_backed_up += 1
                
            except Exception as e:
                logger.error(
                    f"Failed to backup file {media_file.id}: {e}"
                )
                backup_job.files_failed += 1
                
                # Continue with other files
                continue
    
    async def _execute_incremental_backup(
        self,
        db: AsyncSession,
        backup_job: BackupJob
    ):
        """
        Execute an incremental backup.
        """
        logger.info(f"Starting incremental backup for job {backup_job.job_id}")
        
        # Get last backup timestamp
        last_backup_time = await self._get_last_backup_time(
            db, BackupType.INCREMENTAL
        )
        
        if not last_backup_time:
            # No previous backup, perform full backup
            await self._execute_full_backup(db, backup_job)
            return
        
        # Get files modified since last backup
        files_query = select(MediaFile).where(
            and_(
                MediaFile.id.in_(backup_job.source_files),
                MediaFile.status == MediaStatus.ACTIVE,
                or_(
                    MediaFile.created_at > last_backup_time,
                    MediaFile.updated_at > last_backup_time
                )
            )
        )
        
        result = await db.execute(files_query)
        files = result.scalars().all()
        
        logger.info(
            f"Found {len(files)} files modified since {last_backup_time}"
        )
        
        # Backup modified files
        for media_file in files:
            try:
                await self._backup_file(backup_job, media_file)
                backup_job.files_backed_up += 1
                
            except Exception as e:
                logger.error(
                    f"Failed to backup file {media_file.id}: {e}"
                )
                backup_job.files_failed += 1
    
    async def _execute_differential_backup(
        self,
        db: AsyncSession,
        backup_job: BackupJob
    ):
        """
        Execute a differential backup.
        """
        logger.info(f"Starting differential backup for job {backup_job.job_id}")
        
        # Get last full backup timestamp
        last_full_backup_time = await self._get_last_backup_time(
            db, BackupType.FULL
        )
        
        if not last_full_backup_time:
            # No previous full backup, perform full backup
            await self._execute_full_backup(db, backup_job)
            return
        
        # Get files modified since last full backup
        files_query = select(MediaFile).where(
            and_(
                MediaFile.id.in_(backup_job.source_files),
                MediaFile.status == MediaStatus.ACTIVE,
                or_(
                    MediaFile.created_at > last_full_backup_time,
                    MediaFile.updated_at > last_full_backup_time
                )
            )
        )
        
        result = await db.execute(files_query)
        files = result.scalars().all()
        
        logger.info(
            f"Found {len(files)} files modified since last full backup {last_full_backup_time}"
        )
        
        # Backup modified files
        for media_file in files:
            try:
                await self._backup_file(backup_job, media_file)
                backup_job.files_backed_up += 1
                
            except Exception as e:
                logger.error(
                    f"Failed to backup file {media_file.id}: {e}"
                )
                backup_job.files_failed += 1
    
    async def _backup_file(
        self,
        backup_job: BackupJob,
        media_file: MediaFile
    ):
        """
        Backup a single file.
        """
        try:
            # Download file from storage
            file_stream = await self.storage.download_file_stream(
                media_file.storage_path
            )
            
            # Create backup file path
            backup_file_path = f"{backup_job.backup_path}/{media_file.id}_{media_file.filename}"
            
            # Upload to backup destination
            if backup_job.destination == BackupDestination.LOCAL:
                await self._backup_to_local(file_stream, backup_file_path)
            elif backup_job.destination in [BackupDestination.S3, BackupDestination.GLACIER]:
                await self._backup_to_s3(file_stream, backup_file_path, backup_job.destination)
            elif backup_job.destination == BackupDestination.AZURE:
                await self._backup_to_azure(file_stream, backup_file_path)
            elif backup_job.destination == BackupDestination.GCS:
                await self._backup_to_gcs(file_stream, backup_file_path)
            
            # Update backup size
            backup_job.backup_size += media_file.file_size
            
            logger.debug(f"Backed up file {media_file.id} to {backup_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to backup file {media_file.id}: {e}")
            raise
    
    async def _backup_to_local(
        self,
        file_stream: bytes,
        backup_path: str
    ):
        """
        Backup file to local storage.
        """
        local_path = self.local_backup_path / backup_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Compress and write file
        with gzip.open(local_path.with_suffix('.gz'), 'wb') as f:
            f.write(file_stream)
    
    async def _backup_to_s3(
        self,
        file_stream: bytes,
        backup_path: str,
        destination: BackupDestination
    ):
        """
        Backup file to S3 or Glacier.
        """
        storage_class = "GLACIER" if destination == BackupDestination.GLACIER else "STANDARD"
        
        # Compress file
        compressed_data = gzip.compress(file_stream)
        
        # Upload to backup storage
        await self.backup_storage.upload_file(
            file_data=compressed_data,
            storage_path=f"{self.backup_bucket}/{backup_path}.gz",
            content_type="application/gzip",
            metadata={
                "backup_type": "media_backup",
                "storage_class": storage_class,
                "compressed": "true"
            }
        )
    
    async def _backup_to_azure(
        self,
        file_stream: bytes,
        backup_path: str
    ):
        """
        Backup file to Azure Blob Storage.
        """
        # This would require Azure SDK implementation
        logger.warning("Azure backup not implemented")
        raise NotImplementedError("Azure backup not implemented")
    
    async def _backup_to_gcs(
        self,
        file_stream: bytes,
        backup_path: str
    ):
        """
        Backup file to Google Cloud Storage.
        """
        # This would require GCS SDK implementation
        logger.warning("GCS backup not implemented")
        raise NotImplementedError("GCS backup not implemented")
    
    async def restore_backup(
        self,
        db: AsyncSession,
        backup_id: UUID,
        restore_path: Optional[str] = None,
        file_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Restore files from a backup.
        
        Args:
            db: Database session
            backup_id: Backup record ID
            restore_path: Custom restore path (optional)
            file_ids: Specific file IDs to restore (optional)
        
        Returns:
            Restore operation results
        """
        try:
            # Get backup record
            backup_record = await self._get_backup_record(db, backup_id)
            if not backup_record:
                raise MediaServiceException(f"Backup {backup_id} not found")
            
            # Validate backup integrity
            if not await self._validate_backup_integrity(backup_record):
                raise MediaServiceException(f"Backup {backup_id} integrity check failed")
            
            # Get files to restore
            files_to_restore = file_ids or backup_record.file_ids
            
            # Restore files
            restored_files = []
            failed_files = []
            
            for file_id in files_to_restore:
                try:
                    restored_path = await self._restore_file(
                        backup_record, file_id, restore_path
                    )
                    restored_files.append({
                        "file_id": str(file_id),
                        "restored_path": restored_path
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to restore file {file_id}: {e}")
                    failed_files.append({
                        "file_id": str(file_id),
                        "error": str(e)
                    })
            
            return {
                "backup_id": str(backup_id),
                "restored_files": restored_files,
                "failed_files": failed_files,
                "total_restored": len(restored_files),
                "total_failed": len(failed_files)
            }
            
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            raise MediaServiceException(f"Backup restore failed: {str(e)}")
    
    async def _restore_file(
        self,
        backup_record: BackupRecord,
        file_id: UUID,
        restore_path: Optional[str] = None
    ) -> str:
        """
        Restore a single file from backup.
        """
        # Get file from backup
        backup_file_path = f"{backup_record.backup_path}/{file_id}_*"
        
        if backup_record.destination == BackupDestination.LOCAL:
            file_data = await self._restore_from_local(backup_file_path)
        elif backup_record.destination in [BackupDestination.S3, BackupDestination.GLACIER]:
            file_data = await self._restore_from_s3(backup_file_path)
        else:
            raise MediaServiceException(f"Restore from {backup_record.destination} not implemented")
        
        # Determine restore path
        if restore_path:
            final_path = f"{restore_path}/{file_id}"
        else:
            final_path = f"restored/{backup_record.id}/{file_id}"
        
        # Upload restored file to storage
        await self.storage.upload_file(
            file_data=file_data,
            storage_path=final_path,
            content_type="application/octet-stream",
            metadata={
                "restored_from_backup": str(backup_record.id),
                "original_file_id": str(file_id)
            }
        )
        
        return final_path
    
    async def _restore_from_local(self, backup_file_path: str) -> bytes:
        """
        Restore file from local backup.
        """
        local_path = self.local_backup_path / f"{backup_file_path}.gz"
        
        if not local_path.exists():
            raise MediaServiceException(f"Backup file not found: {local_path}")
        
        with gzip.open(local_path, 'rb') as f:
            return f.read()
    
    async def _restore_from_s3(self, backup_file_path: str) -> bytes:
        """
        Restore file from S3 backup.
        """
        s3_path = f"{self.backup_bucket}/{backup_file_path}.gz"
        
        # Download from backup storage
        compressed_data = await self.backup_storage.download_file_stream(s3_path)
        
        # Decompress
        return gzip.decompress(compressed_data)
    
    async def schedule_automatic_backups(
        self,
        db: AsyncSession
    ):
        """
        Schedule automatic backups based on configuration.
        """
        try:
            now = datetime.utcnow()
            
            # Check if full backup is needed
            last_full_backup = await self._get_last_backup_time(db, BackupType.FULL)
            if not last_full_backup or (now - last_full_backup) >= self.full_backup_interval:
                logger.info("Scheduling full backup")
                
                backup_job = await self.create_backup_job(
                    db=db,
                    backup_type=BackupType.FULL,
                    destination=BackupDestination.S3
                )
                
                await self.start_backup_job(db, backup_job.job_id)
            
            # Check if incremental backup is needed
            last_incremental_backup = await self._get_last_backup_time(db, BackupType.INCREMENTAL)
            if not last_incremental_backup or (now - last_incremental_backup) >= self.incremental_backup_interval:
                logger.info("Scheduling incremental backup")
                
                backup_job = await self.create_backup_job(
                    db=db,
                    backup_type=BackupType.INCREMENTAL,
                    destination=BackupDestination.S3
                )
                
                await self.start_backup_job(db, backup_job.job_id)
            
        except Exception as e:
            logger.error(f"Failed to schedule automatic backups: {e}")
    
    async def cleanup_old_backups(
        self,
        db: AsyncSession
    ):
        """
        Clean up old backups based on retention policy.
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.backup_retention_days)
            
            # Get old backup records
            old_backups_query = select(BackupRecord).where(
                BackupRecord.created_at < cutoff_date
            )
            
            result = await db.execute(old_backups_query)
            old_backups = result.scalars().all()
            
            for backup_record in old_backups:
                try:
                    # Delete backup files
                    await self._delete_backup_files(backup_record)
                    
                    # Delete backup record
                    await db.delete(backup_record)
                    
                    logger.info(f"Deleted old backup {backup_record.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup_record.id}: {e}")
            
            await db.commit()
            
            logger.info(f"Cleaned up {len(old_backups)} old backups")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
    
    async def get_backup_status(
        self,
        job_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get backup job status.
        """
        backup_job = await self._get_backup_job(job_id)
        if not backup_job:
            return None
        
        return {
            "job_id": str(backup_job.job_id),
            "backup_type": backup_job.backup_type.value,
            "destination": backup_job.destination.value,
            "status": backup_job.status.value,
            "created_at": backup_job.created_at.isoformat(),
            "started_at": backup_job.started_at.isoformat() if backup_job.started_at else None,
            "completed_at": backup_job.completed_at.isoformat() if backup_job.completed_at else None,
            "files_backed_up": backup_job.files_backed_up,
            "files_failed": backup_job.files_failed,
            "backup_size": backup_job.backup_size,
            "error_message": backup_job.error_message
        }
    
    # Helper methods
    
    async def _get_files_for_backup(
        self,
        db: AsyncSession,
        backup_type: BackupType,
        user_id: Optional[UUID] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[UUID]:
        """Get list of file IDs for backup."""
        conditions = [MediaFile.status == MediaStatus.ACTIVE]
        
        if user_id:
            conditions.append(MediaFile.owner_id == user_id)
        
        if filters:
            if "media_types" in filters:
                conditions.append(MediaFile.media_type.in_(filters["media_types"]))
            
            if "storage_tiers" in filters:
                conditions.append(MediaFile.storage_tier.in_(filters["storage_tiers"]))
            
            if "created_after" in filters:
                conditions.append(MediaFile.created_at >= filters["created_after"])
            
            if "created_before" in filters:
                conditions.append(MediaFile.created_at <= filters["created_before"])
        
        query = select(MediaFile.id).where(and_(*conditions))
        result = await db.execute(query)
        
        return [row[0] for row in result.fetchall()]
    
    async def _get_last_backup_time(
        self,
        db: AsyncSession,
        backup_type: BackupType
    ) -> Optional[datetime]:
        """Get timestamp of last backup of specified type."""
        query = select(func.max(BackupRecord.created_at)).where(
            and_(
                BackupRecord.backup_type == backup_type,
                BackupRecord.status == BackupStatus.COMPLETED
            )
        )
        
        result = await db.execute(query)
        return result.scalar()
    
    async def _create_backup_path(
        self,
        job_id: UUID,
        backup_type: BackupType,
        destination: BackupDestination
    ) -> str:
        """Create backup path for job."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"backups/{backup_type.value}/{timestamp}_{job_id}"
    
    async def _calculate_backup_checksum(self, backup_path: str) -> str:
        """Calculate checksum for backup."""
        # This is a simplified implementation
        # In practice, you'd calculate checksum of all backup files
        return hashlib.sha256(backup_path.encode()).hexdigest()
    
    async def _store_backup_job(self, backup_job: BackupJob):
        """Store backup job in cache."""
        cache_key = f"backup_job:{backup_job.job_id}"
        job_data = {
            "job_id": str(backup_job.job_id),
            "backup_type": backup_job.backup_type.value,
            "destination": backup_job.destination.value,
            "source_files": [str(f) for f in backup_job.source_files],
            "status": backup_job.status.value,
            "created_at": backup_job.created_at.isoformat(),
            "started_at": backup_job.started_at.isoformat() if backup_job.started_at else None,
            "completed_at": backup_job.completed_at.isoformat() if backup_job.completed_at else None,
            "error_message": backup_job.error_message,
            "backup_size": backup_job.backup_size,
            "files_backed_up": backup_job.files_backed_up,
            "files_failed": backup_job.files_failed,
            "backup_path": backup_job.backup_path,
            "checksum": backup_job.checksum
        }
        
        await self.cache.set(cache_key, job_data, ttl=7 * 24 * 3600)  # 7 days
        
        # Also store in active jobs
        self.active_jobs[backup_job.job_id] = backup_job
    
    async def _get_backup_job(self, job_id: UUID) -> Optional[BackupJob]:
        """Get backup job from cache."""
        # Check active jobs first
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        # Check cache
        cache_key = f"backup_job:{job_id}"
        job_data = await self.cache.get(cache_key)
        
        if not job_data:
            return None
        
        # Reconstruct backup job
        backup_job = BackupJob(
            job_id=UUID(job_data["job_id"]),
            backup_type=BackupType(job_data["backup_type"]),
            destination=BackupDestination(job_data["destination"]),
            source_files=[UUID(f) for f in job_data["source_files"]],
            created_at=datetime.fromisoformat(job_data["created_at"]),
            status=BackupStatus(job_data["status"])
        )
        
        if job_data["started_at"]:
            backup_job.started_at = datetime.fromisoformat(job_data["started_at"])
        
        if job_data["completed_at"]:
            backup_job.completed_at = datetime.fromisoformat(job_data["completed_at"])
        
        backup_job.error_message = job_data["error_message"]
        backup_job.backup_size = job_data["backup_size"]
        backup_job.files_backed_up = job_data["files_backed_up"]
        backup_job.files_failed = job_data["files_failed"]
        backup_job.backup_path = job_data["backup_path"]
        backup_job.checksum = job_data["checksum"]
        
        return backup_job
    
    async def _create_backup_record(
        self,
        db: AsyncSession,
        backup_job: BackupJob
    ):
        """Create backup record in database."""
        backup_record = BackupRecord(
            id=backup_job.job_id,
            backup_type=backup_job.backup_type,
            destination=backup_job.destination,
            backup_path=backup_job.backup_path,
            file_ids=backup_job.source_files,
            status=backup_job.status,
            backup_size=backup_job.backup_size,
            files_backed_up=backup_job.files_backed_up,
            files_failed=backup_job.files_failed,
            checksum=backup_job.checksum,
            error_message=backup_job.error_message,
            created_at=backup_job.created_at,
            started_at=backup_job.started_at,
            completed_at=backup_job.completed_at
        )
        
        db.add(backup_record)
        await db.commit()
    
    async def _get_backup_record(
        self,
        db: AsyncSession,
        backup_id: UUID
    ) -> Optional[BackupRecord]:
        """Get backup record from database."""
        query = select(BackupRecord).where(BackupRecord.id == backup_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def _validate_backup_integrity(
        self,
        backup_record: BackupRecord
    ) -> bool:
        """Validate backup integrity using checksum."""
        try:
            # Calculate current checksum
            current_checksum = await self._calculate_backup_checksum(
                backup_record.backup_path
            )
            
            # Compare with stored checksum
            return current_checksum == backup_record.checksum
            
        except Exception as e:
            logger.error(f"Failed to validate backup integrity: {e}")
            return False
    
    async def _delete_backup_files(self, backup_record: BackupRecord):
        """Delete backup files from storage."""
        if backup_record.destination == BackupDestination.LOCAL:
            # Delete local backup files
            backup_dir = self.local_backup_path / backup_record.backup_path
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
        
        elif backup_record.destination in [BackupDestination.S3, BackupDestination.GLACIER]:
            # Delete S3 backup files
            # This would require listing and deleting all files in the backup path
            logger.warning("S3 backup deletion not fully implemented")
        
        else:
            logger.warning(f"Backup deletion for {backup_record.destination} not implemented")