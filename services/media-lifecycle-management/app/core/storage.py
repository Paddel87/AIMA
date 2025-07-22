#!/usr/bin/env python3
"""
Object storage configuration for the AIMA Media Lifecycle Management Service.

This module provides MinIO/S3 storage management for media files,
including upload, download, and lifecycle management.
"""

import os
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, BinaryIO, AsyncGenerator
from pathlib import Path
import asyncio
from urllib.parse import urlparse

import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
import structlog
from PIL import Image
import magic

from app.core.config import get_settings
from app.core.database import MediaType, StorageTier

logger = structlog.get_logger(__name__)


class StorageManager:
    """Object storage manager for media files."""
    
    def __init__(self):
        self.settings = get_settings()
        self.session = None
        self.s3_client = None
        
        # Storage configuration
        self.bucket_name = self.settings.STORAGE_BUCKET_NAME
        self.region = self.settings.STORAGE_REGION
        
        # File type mappings
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
        self.video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v'}
        self.audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'}
        self.document_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt'}
    
    async def initialize(self):
        """Initialize storage connection."""
        try:
            # Configure boto3 session
            config = Config(
                region_name=self.region,
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                max_pool_connections=50
            )
            
            self.session = aioboto3.Session(
                aws_access_key_id=self.settings.STORAGE_ACCESS_KEY,
                aws_secret_access_key=self.settings.STORAGE_SECRET_KEY
            )
            
            # Create S3 client
            self.s3_client = self.session.client(
                's3',
                endpoint_url=self.settings.STORAGE_ENDPOINT,
                config=config
            )
            
            # Ensure bucket exists
            await self._ensure_bucket_exists()
            
            logger.info("Storage manager initialized successfully", bucket=self.bucket_name)
            
        except Exception as e:
            logger.error("Failed to initialize storage manager", error=str(e))
            raise
    
    async def close(self):
        """Close storage connections."""
        if self.s3_client:
            await self.s3_client.close()
            logger.info("Storage connections closed")
    
    async def _ensure_bucket_exists(self):
        """Ensure the storage bucket exists."""
        try:
            await self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    await self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                    logger.info("Storage bucket created", bucket=self.bucket_name)
                except ClientError as create_error:
                    logger.error("Failed to create bucket", bucket=self.bucket_name, error=str(create_error))
                    raise
            else:
                logger.error("Failed to access bucket", bucket=self.bucket_name, error=str(e))
                raise
    
    def _get_media_type(self, filename: str, mime_type: str) -> MediaType:
        """Determine media type from filename and MIME type."""
        ext = Path(filename).suffix.lower()
        
        if ext in self.image_extensions or mime_type.startswith('image/'):
            return MediaType.IMAGE
        elif ext in self.video_extensions or mime_type.startswith('video/'):
            return MediaType.VIDEO
        elif ext in self.audio_extensions or mime_type.startswith('audio/'):
            return MediaType.AUDIO
        elif ext in self.document_extensions or mime_type.startswith('application/'):
            return MediaType.DOCUMENT
        else:
            return MediaType.OTHER
    
    def _generate_storage_path(self, filename: str, media_type: MediaType, user_id: Optional[str] = None) -> str:
        """Generate storage path for file."""
        # Create date-based directory structure
        now = datetime.utcnow()
        date_path = f"{now.year:04d}/{now.month:02d}/{now.day:02d}"
        
        # Add media type directory
        type_path = media_type.value
        
        # Add user directory if provided
        user_path = f"user_{user_id}" if user_id else "anonymous"
        
        # Generate unique filename
        timestamp = int(now.timestamp() * 1000000)  # microseconds
        name, ext = os.path.splitext(filename)
        safe_filename = f"{timestamp}_{name[:50]}{ext}"
        
        return f"{type_path}/{user_path}/{date_path}/{safe_filename}"
    
    async def _calculate_file_hash(self, file_data: bytes) -> str:
        """Calculate SHA-256 hash of file data."""
        return hashlib.sha256(file_data).hexdigest()
    
    async def _detect_mime_type(self, file_data: bytes, filename: str) -> str:
        """Detect MIME type of file."""
        try:
            # Use python-magic for accurate detection
            mime_type = magic.from_buffer(file_data, mime=True)
            return mime_type
        except Exception:
            # Fallback to filename-based detection
            mime_type, _ = mimetypes.guess_type(filename)
            return mime_type or 'application/octet-stream'
    
    async def _extract_image_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """Extract metadata from image files."""
        try:
            from io import BytesIO
            image = Image.open(BytesIO(file_data))
            
            metadata = {
                'width': image.width,
                'height': image.height,
                'format': image.format,
                'mode': image.mode
            }
            
            # Extract EXIF data if available
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                if exif:
                    metadata['exif'] = {str(k): str(v) for k, v in exif.items()}
            
            return metadata
            
        except Exception as e:
            logger.warning("Failed to extract image metadata", error=str(e))
            return {}
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        user_id: Optional[str] = None,
        storage_tier: StorageTier = StorageTier.HOT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload file to object storage.
        
        Returns:
            Dict containing file information including storage_path, file_hash, etc.
        """
        try:
            # Detect MIME type
            mime_type = await self._detect_mime_type(file_data, filename)
            media_type = self._get_media_type(filename, mime_type)
            
            # Calculate file hash
            file_hash = await self._calculate_file_hash(file_data)
            
            # Generate storage path
            storage_path = self._generate_storage_path(filename, media_type, user_id)
            
            # Prepare metadata
            upload_metadata = {
                'original_filename': filename,
                'mime_type': mime_type,
                'media_type': media_type.value,
                'file_hash': file_hash,
                'file_size': str(len(file_data)),
                'upload_timestamp': datetime.utcnow().isoformat(),
                'storage_tier': storage_tier.value
            }
            
            if user_id:
                upload_metadata['uploaded_by'] = user_id
            
            if metadata:
                upload_metadata.update({f'custom_{k}': str(v) for k, v in metadata.items()})
            
            # Extract media-specific metadata
            if media_type == MediaType.IMAGE:
                image_metadata = await self._extract_image_metadata(file_data)
                upload_metadata.update(image_metadata)
            
            # Set storage class based on tier
            storage_class = self._get_storage_class(storage_tier)
            
            # Upload to S3
            await self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_path,
                Body=file_data,
                ContentType=mime_type,
                Metadata=upload_metadata,
                StorageClass=storage_class
            )
            
            logger.info(
                "File uploaded successfully",
                filename=filename,
                storage_path=storage_path,
                size=len(file_data),
                media_type=media_type.value
            )
            
            return {
                'storage_path': storage_path,
                'storage_bucket': self.bucket_name,
                'file_hash': file_hash,
                'mime_type': mime_type,
                'media_type': media_type,
                'file_size': len(file_data),
                'metadata': upload_metadata
            }
            
        except Exception as e:
            logger.error("File upload failed", filename=filename, error=str(e))
            raise
    
    def _get_storage_class(self, storage_tier: StorageTier) -> str:
        """Get S3 storage class based on storage tier."""
        mapping = {
            StorageTier.HOT: 'STANDARD',
            StorageTier.WARM: 'STANDARD_IA',
            StorageTier.COLD: 'GLACIER',
            StorageTier.ARCHIVE: 'DEEP_ARCHIVE'
        }
        return mapping.get(storage_tier, 'STANDARD')
    
    async def download_file(self, storage_path: str) -> bytes:
        """Download file from object storage."""
        try:
            response = await self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            file_data = await response['Body'].read()
            
            logger.info("File downloaded successfully", storage_path=storage_path, size=len(file_data))
            return file_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning("File not found", storage_path=storage_path)
                raise FileNotFoundError(f"File not found: {storage_path}")
            else:
                logger.error("File download failed", storage_path=storage_path, error=str(e))
                raise
    
    async def download_file_stream(self, storage_path: str) -> AsyncGenerator[bytes, None]:
        """Download file as stream from object storage."""
        try:
            response = await self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            async for chunk in response['Body'].iter_chunks(chunk_size=8192):
                yield chunk
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.warning("File not found for streaming", storage_path=storage_path)
                raise FileNotFoundError(f"File not found: {storage_path}")
            else:
                logger.error("File stream failed", storage_path=storage_path, error=str(e))
                raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """Delete file from object storage."""
        try:
            await self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            logger.info("File deleted successfully", storage_path=storage_path)
            return True
            
        except ClientError as e:
            logger.error("File deletion failed", storage_path=storage_path, error=str(e))
            return False
    
    async def file_exists(self, storage_path: str) -> bool:
        """Check if file exists in object storage."""
        try:
            await self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                logger.error("File existence check failed", storage_path=storage_path, error=str(e))
                raise
    
    async def get_file_metadata(self, storage_path: str) -> Dict[str, Any]:
        """Get file metadata from object storage."""
        try:
            response = await self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_path
            )
            
            return {
                'content_length': response.get('ContentLength'),
                'content_type': response.get('ContentType'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag'),
                'storage_class': response.get('StorageClass'),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"File not found: {storage_path}")
            else:
                logger.error("Failed to get file metadata", storage_path=storage_path, error=str(e))
                raise
    
    async def generate_presigned_url(
        self,
        storage_path: str,
        expiration: int = 3600,
        method: str = 'GET'
    ) -> str:
        """Generate presigned URL for file access."""
        try:
            url = await self.s3_client.generate_presigned_url(
                method.lower() + '_object',
                Params={'Bucket': self.bucket_name, 'Key': storage_path},
                ExpiresIn=expiration
            )
            
            logger.info(
                "Presigned URL generated",
                storage_path=storage_path,
                method=method,
                expiration=expiration
            )
            
            return url
            
        except Exception as e:
            logger.error("Failed to generate presigned URL", storage_path=storage_path, error=str(e))
            raise
    
    async def copy_file(self, source_path: str, destination_path: str) -> bool:
        """Copy file within object storage."""
        try:
            copy_source = {'Bucket': self.bucket_name, 'Key': source_path}
            
            await self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=destination_path
            )
            
            logger.info("File copied successfully", source=source_path, destination=destination_path)
            return True
            
        except ClientError as e:
            logger.error("File copy failed", source=source_path, destination=destination_path, error=str(e))
            return False
    
    async def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[Dict[str, Any]]:
        """List files in object storage."""
        try:
            response = await self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'],
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })
            
            return files
            
        except ClientError as e:
            logger.error("Failed to list files", prefix=prefix, error=str(e))
            raise
    
    async def get_storage_usage(self) -> Dict[str, Any]:
        """Get storage usage statistics."""
        try:
            # This is a simplified version - in production, you might want to use CloudWatch metrics
            response = await self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            total_size = 0
            total_files = 0
            
            for obj in response.get('Contents', []):
                total_size += obj['Size']
                total_files += 1
            
            return {
                'total_files': total_files,
                'total_size': total_size,
                'bucket_name': self.bucket_name
            }
            
        except ClientError as e:
            logger.error("Failed to get storage usage", error=str(e))
            raise


# Global storage manager instance
storage_manager = StorageManager()


async def init_storage():
    """Initialize storage manager."""
    await storage_manager.initialize()
    logger.info("Storage manager initialized")


async def close_storage():
    """Close storage connections."""
    await storage_manager.close()


def get_storage() -> StorageManager:
    """Get storage manager instance."""
    return storage_manager