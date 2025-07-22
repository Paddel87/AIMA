#!/usr/bin/env python3
"""
Media management API routes for the AIMA Media Lifecycle Management Service.

This module provides REST API endpoints for media upload, download,
metadata management, and lifecycle operations.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from io import BytesIO

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form,
    Query, Path, BackgroundTasks, Response, Request
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from pydantic import BaseModel, Field, validator
import structlog

from app.core.database import get_db, MediaFile, MediaTag, ProcessingJob, MediaType, MediaStatus, StorageTier
from app.core.storage import get_storage
from app.core.redis_client import get_cache, get_rate_limiter
from app.core.config import get_settings
from app.api.dependencies import get_current_user, require_permissions
from app.services.media_processor import get_media_processor
from app.services.metadata_extractor import get_metadata_extractor

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/media", tags=["media"])
settings = get_settings()


# Pydantic models
class MediaFileResponse(BaseModel):
    """Media file response model."""
    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    media_type: str
    status: str
    storage_tier: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    thumbnail_path: Optional[str] = None
    preview_path: Optional[str] = None
    uploaded_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    tags: List[Dict[str, str]] = []

    class Config:
        from_attributes = True


class MediaUploadResponse(BaseModel):
    """Media upload response model."""
    id: uuid.UUID
    filename: str
    status: str
    upload_url: Optional[str] = None
    message: str


class MediaListResponse(BaseModel):
    """Media list response model."""
    items: List[MediaFileResponse]
    total: int
    page: int
    size: int
    pages: int


class MediaTagRequest(BaseModel):
    """Media tag request model."""
    tag_name: str = Field(..., min_length=1, max_length=100)
    tag_value: Optional[str] = Field(None, max_length=255)


class MediaUpdateRequest(BaseModel):
    """Media update request model."""
    filename: Optional[str] = Field(None, min_length=1, max_length=255)
    storage_tier: Optional[StorageTier] = None
    tags: Optional[List[MediaTagRequest]] = None


class MediaSearchRequest(BaseModel):
    """Media search request model."""
    query: Optional[str] = None
    media_type: Optional[MediaType] = None
    status: Optional[MediaStatus] = None
    storage_tier: Optional[StorageTier] = None
    uploaded_by: Optional[uuid.UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: Optional[Dict[str, str]] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None


@router.post("/upload", response_model=MediaUploadResponse)
async def upload_media(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    storage_tier: StorageTier = Form(StorageTier.HOT),
    tags: Optional[str] = Form(None),  # JSON string of tags
    auto_process: bool = Form(True),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:upload"]))
):
    """Upload a media file."""
    try:
        # Rate limiting
        rate_limiter = get_rate_limiter()
        user_id = current_user.get("id")
        is_allowed, rate_info = await rate_limiter.is_allowed(
            f"upload:{user_id}", 
            limit=settings.UPLOAD_RATE_LIMIT_PER_HOUR, 
            window=3600
        )
        
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail="Upload rate limit exceeded",
                headers={"X-RateLimit-Remaining": str(rate_info["remaining"])}
            )
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Read file data
        file_data = await file.read()
        
        # Validate file size
        if len(file_data) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
            )
        
        if len(file_data) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Upload to storage
        storage = get_storage()
        upload_result = await storage.upload_file(
            file_data=file_data,
            filename=file.filename,
            user_id=str(user_id),
            storage_tier=storage_tier
        )
        
        # Parse tags if provided
        parsed_tags = []
        if tags:
            try:
                import json
                tag_data = json.loads(tags)
                parsed_tags = [MediaTagRequest(**tag) for tag in tag_data]
            except Exception as e:
                logger.warning("Failed to parse tags", tags=tags, error=str(e))
        
        # Create database record
        media_file = MediaFile(
            filename=upload_result["storage_path"].split("/")[-1],
            original_filename=file.filename,
            mime_type=upload_result["mime_type"],
            file_size=upload_result["file_size"],
            file_hash=upload_result["file_hash"],
            media_type=upload_result["media_type"].value,
            status=MediaStatus.UPLOADED,
            storage_path=upload_result["storage_path"],
            storage_bucket=upload_result["storage_bucket"],
            storage_tier=storage_tier.value,
            metadata=upload_result["metadata"],
            uploaded_by=user_id,
            upload_ip=request.client.host,
            upload_user_agent=request.headers.get("user-agent")
        )
        
        # Extract basic metadata
        if "width" in upload_result["metadata"]:
            media_file.width = upload_result["metadata"]["width"]
        if "height" in upload_result["metadata"]:
            media_file.height = upload_result["metadata"]["height"]
        
        db.add(media_file)
        await db.flush()  # Get the ID
        
        # Add tags
        for tag_req in parsed_tags:
            tag = MediaTag(
                media_file_id=media_file.id,
                tag_name=tag_req.tag_name,
                tag_value=tag_req.tag_value
            )
            db.add(tag)
        
        await db.commit()
        
        # Schedule background processing if requested
        if auto_process:
            background_tasks.add_task(
                process_media_background,
                str(media_file.id),
                upload_result["media_type"]
            )
        
        logger.info(
            "Media file uploaded successfully",
            file_id=str(media_file.id),
            filename=file.filename,
            size=len(file_data),
            user_id=str(user_id)
        )
        
        return MediaUploadResponse(
            id=media_file.id,
            filename=media_file.filename,
            status=media_file.status,
            message="File uploaded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Media upload failed", filename=file.filename, error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Upload failed")


@router.get("/", response_model=MediaListResponse)
async def list_media(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    media_type: Optional[MediaType] = Query(None),
    status: Optional[MediaStatus] = Query(None),
    storage_tier: Optional[StorageTier] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|filename|file_size|updated_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:read"]))
):
    """List media files with filtering and pagination."""
    try:
        # Build query
        query = select(MediaFile).where(MediaFile.is_deleted == False)
        
        # Apply filters
        if media_type:
            query = query.where(MediaFile.media_type == media_type.value)
        
        if status:
            query = query.where(MediaFile.status == status.value)
        
        if storage_tier:
            query = query.where(MediaFile.storage_tier == storage_tier.value)
        
        if search:
            search_filter = or_(
                MediaFile.filename.ilike(f"%{search}%"),
                MediaFile.original_filename.ilike(f"%{search}%")
            )
            query = query.where(search_filter)
        
        # Apply sorting
        sort_column = getattr(MediaFile, sort_by)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * size
        query = query.offset(offset).limit(size)
        
        # Execute query
        result = await db.execute(query)
        media_files = result.scalars().all()
        
        # Convert to response models
        items = []
        for media_file in media_files:
            # Get tags
            tags_query = select(MediaTag).where(MediaTag.media_file_id == media_file.id)
            tags_result = await db.execute(tags_query)
            tags = tags_result.scalars().all()
            
            media_response = MediaFileResponse(
                id=media_file.id,
                filename=media_file.filename,
                original_filename=media_file.original_filename,
                mime_type=media_file.mime_type,
                file_size=media_file.file_size,
                media_type=media_file.media_type,
                status=media_file.status,
                storage_tier=media_file.storage_tier,
                width=media_file.width,
                height=media_file.height,
                duration=media_file.duration,
                metadata=media_file.metadata,
                thumbnail_path=media_file.thumbnail_path,
                preview_path=media_file.preview_path,
                uploaded_by=media_file.uploaded_by,
                created_at=media_file.created_at,
                updated_at=media_file.updated_at,
                tags=[{"name": tag.tag_name, "value": tag.tag_value} for tag in tags]
            )
            items.append(media_response)
        
        pages = (total + size - 1) // size
        
        return MediaListResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
        
    except Exception as e:
        logger.error("Failed to list media files", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve media files")


@router.get("/{file_id}", response_model=MediaFileResponse)
async def get_media(
    file_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:read"]))
):
    """Get media file details."""
    try:
        # Get media file
        query = select(MediaFile).where(
            and_(MediaFile.id == file_id, MediaFile.is_deleted == False)
        )
        result = await db.execute(query)
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        # Get tags
        tags_query = select(MediaTag).where(MediaTag.media_file_id == file_id)
        tags_result = await db.execute(tags_query)
        tags = tags_result.scalars().all()
        
        # Update access time
        media_file.accessed_at = datetime.utcnow()
        await db.commit()
        
        return MediaFileResponse(
            id=media_file.id,
            filename=media_file.filename,
            original_filename=media_file.original_filename,
            mime_type=media_file.mime_type,
            file_size=media_file.file_size,
            media_type=media_file.media_type,
            status=media_file.status,
            storage_tier=media_file.storage_tier,
            width=media_file.width,
            height=media_file.height,
            duration=media_file.duration,
            metadata=media_file.metadata,
            thumbnail_path=media_file.thumbnail_path,
            preview_path=media_file.preview_path,
            uploaded_by=media_file.uploaded_by,
            created_at=media_file.created_at,
            updated_at=media_file.updated_at,
            tags=[{"name": tag.tag_name, "value": tag.tag_value} for tag in tags]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get media file", file_id=str(file_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve media file")


@router.get("/{file_id}/download")
async def download_media(
    file_id: uuid.UUID = Path(...),
    thumbnail: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:download"]))
):
    """Download media file or thumbnail."""
    try:
        # Get media file
        query = select(MediaFile).where(
            and_(MediaFile.id == file_id, MediaFile.is_deleted == False)
        )
        result = await db.execute(query)
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        # Determine which file to download
        if thumbnail and media_file.thumbnail_path:
            storage_path = media_file.thumbnail_path
            filename = f"thumb_{media_file.original_filename}"
        else:
            storage_path = media_file.storage_path
            filename = media_file.original_filename
        
        # Get file from storage
        storage = get_storage()
        
        # Check if file exists
        if not await storage.file_exists(storage_path):
            raise HTTPException(status_code=404, detail="File not found in storage")
        
        # Stream file
        file_stream = storage.download_file_stream(storage_path)
        
        # Update access time
        media_file.accessed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(
            "Media file download started",
            file_id=str(file_id),
            filename=filename,
            thumbnail=thumbnail,
            user_id=str(current_user.get("id"))
        )
        
        return StreamingResponse(
            file_stream,
            media_type=media_file.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Media download failed", file_id=str(file_id), error=str(e))
        raise HTTPException(status_code=500, detail="Download failed")


@router.put("/{file_id}", response_model=MediaFileResponse)
async def update_media(
    file_id: uuid.UUID = Path(...),
    update_data: MediaUpdateRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:update"]))
):
    """Update media file metadata."""
    try:
        # Get media file
        query = select(MediaFile).where(
            and_(MediaFile.id == file_id, MediaFile.is_deleted == False)
        )
        result = await db.execute(query)
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        # Update fields
        if update_data.filename:
            media_file.filename = update_data.filename
        
        if update_data.storage_tier:
            media_file.storage_tier = update_data.storage_tier.value
        
        media_file.updated_at = datetime.utcnow()
        
        # Update tags if provided
        if update_data.tags is not None:
            # Delete existing tags
            await db.execute(
                select(MediaTag).where(MediaTag.media_file_id == file_id)
            )
            
            # Add new tags
            for tag_req in update_data.tags:
                tag = MediaTag(
                    media_file_id=file_id,
                    tag_name=tag_req.tag_name,
                    tag_value=tag_req.tag_value
                )
                db.add(tag)
        
        await db.commit()
        
        # Get updated tags
        tags_query = select(MediaTag).where(MediaTag.media_file_id == file_id)
        tags_result = await db.execute(tags_query)
        tags = tags_result.scalars().all()
        
        logger.info("Media file updated", file_id=str(file_id), user_id=str(current_user.get("id")))
        
        return MediaFileResponse(
            id=media_file.id,
            filename=media_file.filename,
            original_filename=media_file.original_filename,
            mime_type=media_file.mime_type,
            file_size=media_file.file_size,
            media_type=media_file.media_type,
            status=media_file.status,
            storage_tier=media_file.storage_tier,
            width=media_file.width,
            height=media_file.height,
            duration=media_file.duration,
            metadata=media_file.metadata,
            thumbnail_path=media_file.thumbnail_path,
            preview_path=media_file.preview_path,
            uploaded_by=media_file.uploaded_by,
            created_at=media_file.created_at,
            updated_at=media_file.updated_at,
            tags=[{"name": tag.tag_name, "value": tag.tag_value} for tag in tags]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update media file", file_id=str(file_id), error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Update failed")


@router.delete("/{file_id}")
async def delete_media(
    file_id: uuid.UUID = Path(...),
    permanent: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:delete"]))
):
    """Delete media file (soft delete by default)."""
    try:
        # Get media file
        query = select(MediaFile).where(
            and_(MediaFile.id == file_id, MediaFile.is_deleted == False)
        )
        result = await db.execute(query)
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        if permanent:
            # Permanent deletion - remove from storage and database
            storage = get_storage()
            
            # Delete main file
            await storage.delete_file(media_file.storage_path)
            
            # Delete thumbnail if exists
            if media_file.thumbnail_path:
                await storage.delete_file(media_file.thumbnail_path)
            
            # Delete preview if exists
            if media_file.preview_path:
                await storage.delete_file(media_file.preview_path)
            
            # Delete from database
            await db.delete(media_file)
            
        else:
            # Soft delete
            media_file.is_deleted = True
            media_file.deleted_at = datetime.utcnow()
            media_file.status = MediaStatus.DELETED
        
        await db.commit()
        
        logger.info(
            "Media file deleted",
            file_id=str(file_id),
            permanent=permanent,
            user_id=str(current_user.get("id"))
        )
        
        return {"message": "Media file deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete media file", file_id=str(file_id), error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Deletion failed")


@router.get("/{file_id}/url")
async def get_media_url(
    file_id: uuid.UUID = Path(...),
    expiration: int = Query(3600, ge=60, le=86400),
    thumbnail: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
    _: None = Depends(require_permissions(["media:read"]))
):
    """Get presigned URL for media file access."""
    try:
        # Get media file
        query = select(MediaFile).where(
            and_(MediaFile.id == file_id, MediaFile.is_deleted == False)
        )
        result = await db.execute(query)
        media_file = result.scalar_one_or_none()
        
        if not media_file:
            raise HTTPException(status_code=404, detail="Media file not found")
        
        # Determine which file to get URL for
        if thumbnail and media_file.thumbnail_path:
            storage_path = media_file.thumbnail_path
        else:
            storage_path = media_file.storage_path
        
        # Generate presigned URL
        storage = get_storage()
        url = await storage.generate_presigned_url(
            storage_path=storage_path,
            expiration=expiration,
            method="GET"
        )
        
        # Update access time
        media_file.accessed_at = datetime.utcnow()
        await db.commit()
        
        return {
            "url": url,
            "expires_in": expiration,
            "expires_at": datetime.utcnow().timestamp() + expiration
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate media URL", file_id=str(file_id), error=str(e))
        raise HTTPException(status_code=500, detail="URL generation failed")


async def process_media_background(file_id: str, media_type: MediaType):
    """Background task for media processing."""
    try:
        processor = get_media_processor()
        await processor.process_media(uuid.UUID(file_id), media_type)
        logger.info("Background media processing completed", file_id=file_id)
    except Exception as e:
        logger.error("Background media processing failed", file_id=file_id, error=str(e))