#!/usr/bin/env python3
"""
Media processing service for the AIMA Media Lifecycle Management Service.

This module provides media processing capabilities including thumbnail generation,
metadata extraction, video transcoding, and other media operations using FFmpeg.
"""

import os
import uuid
import asyncio
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import subprocess
from io import BytesIO

import ffmpeg
from PIL import Image, ImageOps
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db, MediaFile, ProcessingJob, MediaType, MediaStatus
from app.core.storage import get_storage
from app.core.config import get_settings
from app.services.metadata_extractor import get_metadata_extractor

logger = structlog.get_logger(__name__)


class MediaProcessor:
    """Media processing service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.temp_dir = Path(tempfile.gettempdir()) / "aima_media_processing"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Processing settings
        self.thumbnail_sizes = {
            "small": (150, 150),
            "medium": (300, 300),
            "large": (600, 600)
        }
        
        self.video_presets = {
            "web_low": {
                "video_codec": "libx264",
                "audio_codec": "aac",
                "video_bitrate": "500k",
                "audio_bitrate": "128k",
                "resolution": "720x480",
                "fps": 24
            },
            "web_medium": {
                "video_codec": "libx264",
                "audio_codec": "aac",
                "video_bitrate": "1000k",
                "audio_bitrate": "192k",
                "resolution": "1280x720",
                "fps": 30
            },
            "web_high": {
                "video_codec": "libx264",
                "audio_codec": "aac",
                "video_bitrate": "2000k",
                "audio_bitrate": "256k",
                "resolution": "1920x1080",
                "fps": 30
            }
        }
    
    async def process_media(self, file_id: uuid.UUID, media_type: MediaType) -> bool:
        """Process media file based on its type."""
        try:
            logger.info("Starting media processing", file_id=str(file_id), media_type=media_type.value)
            
            # Get database session
            async for db in get_db():
                # Get media file
                query = select(MediaFile).where(MediaFile.id == file_id)
                result = await db.execute(query)
                media_file = result.scalar_one_or_none()
                
                if not media_file:
                    logger.error("Media file not found", file_id=str(file_id))
                    return False
                
                # Update status to processing
                media_file.status = MediaStatus.PROCESSING
                media_file.processing_started_at = datetime.utcnow()
                await db.commit()
                
                try:
                    # Process based on media type
                    if media_type == MediaType.IMAGE:
                        success = await self._process_image(media_file, db)
                    elif media_type == MediaType.VIDEO:
                        success = await self._process_video(media_file, db)
                    elif media_type == MediaType.AUDIO:
                        success = await self._process_audio(media_file, db)
                    else:
                        success = await self._process_document(media_file, db)
                    
                    # Update final status
                    if success:
                        media_file.status = MediaStatus.PROCESSED
                        media_file.processing_completed_at = datetime.utcnow()
                        logger.info("Media processing completed successfully", file_id=str(file_id))
                    else:
                        media_file.status = MediaStatus.FAILED
                        media_file.processing_error = "Processing failed"
                        logger.error("Media processing failed", file_id=str(file_id))
                    
                    await db.commit()
                    return success
                    
                except Exception as e:
                    # Update status to failed
                    media_file.status = MediaStatus.FAILED
                    media_file.processing_error = str(e)
                    await db.commit()
                    logger.error("Media processing error", file_id=str(file_id), error=str(e))
                    return False
                
                break  # Exit the async generator
            
        except Exception as e:
            logger.error("Media processing failed", file_id=str(file_id), error=str(e))
            return False
    
    async def _process_image(self, media_file: MediaFile, db: AsyncSession) -> bool:
        """Process image file - generate thumbnails and extract metadata."""
        try:
            storage = get_storage()
            
            # Download original file
            file_data = await storage.download_file(media_file.storage_path)
            
            # Open image
            image = Image.open(BytesIO(file_data))
            
            # Extract and update metadata
            metadata_extractor = get_metadata_extractor()
            metadata = await metadata_extractor.extract_image_metadata(file_data)
            
            # Update media file with extracted metadata
            if metadata:
                media_file.width = metadata.get("width", media_file.width)
                media_file.height = metadata.get("height", media_file.height)
                
                # Merge metadata
                if media_file.metadata:
                    media_file.metadata.update(metadata)
                else:
                    media_file.metadata = metadata
            
            # Generate thumbnails
            thumbnail_data = await self._generate_image_thumbnail(image)
            if thumbnail_data:
                # Upload thumbnail
                thumbnail_filename = f"thumb_{media_file.filename}"
                thumbnail_result = await storage.upload_file(
                    file_data=thumbnail_data,
                    filename=thumbnail_filename,
                    user_id=str(media_file.uploaded_by) if media_file.uploaded_by else None
                )
                media_file.thumbnail_path = thumbnail_result["storage_path"]
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error("Image processing failed", file_id=str(media_file.id), error=str(e))
            return False
    
    async def _process_video(self, media_file: MediaFile, db: AsyncSession) -> bool:
        """Process video file - generate thumbnails, extract metadata, and create previews."""
        try:
            storage = get_storage()
            
            # Download original file
            file_data = await storage.download_file(media_file.storage_path)
            
            # Create temporary file
            temp_input = self.temp_dir / f"input_{media_file.id}.tmp"
            with open(temp_input, "wb") as f:
                f.write(file_data)
            
            try:
                # Extract metadata using FFmpeg
                metadata = await self._extract_video_metadata(str(temp_input))
                
                # Update media file with metadata
                if metadata:
                    media_file.width = metadata.get("width", media_file.width)
                    media_file.height = metadata.get("height", media_file.height)
                    media_file.duration = metadata.get("duration", media_file.duration)
                    media_file.bitrate = metadata.get("bitrate", media_file.bitrate)
                    media_file.frame_rate = metadata.get("frame_rate", media_file.frame_rate)
                    
                    # Merge metadata
                    if media_file.metadata:
                        media_file.metadata.update(metadata)
                    else:
                        media_file.metadata = metadata
                
                # Generate video thumbnail
                thumbnail_data = await self._generate_video_thumbnail(str(temp_input))
                if thumbnail_data:
                    thumbnail_filename = f"thumb_{media_file.filename}.jpg"
                    thumbnail_result = await storage.upload_file(
                        file_data=thumbnail_data,
                        filename=thumbnail_filename,
                        user_id=str(media_file.uploaded_by) if media_file.uploaded_by else None
                    )
                    media_file.thumbnail_path = thumbnail_result["storage_path"]
                
                # Generate web-optimized preview if needed
                if self.settings.GENERATE_VIDEO_PREVIEWS:
                    preview_data = await self._generate_video_preview(str(temp_input))
                    if preview_data:
                        preview_filename = f"preview_{media_file.filename}"
                        preview_result = await storage.upload_file(
                            file_data=preview_data,
                            filename=preview_filename,
                            user_id=str(media_file.uploaded_by) if media_file.uploaded_by else None
                        )
                        media_file.preview_path = preview_result["storage_path"]
                
            finally:
                # Clean up temporary file
                if temp_input.exists():
                    temp_input.unlink()
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error("Video processing failed", file_id=str(media_file.id), error=str(e))
            return False
    
    async def _process_audio(self, media_file: MediaFile, db: AsyncSession) -> bool:
        """Process audio file - extract metadata and generate waveform."""
        try:
            storage = get_storage()
            
            # Download original file
            file_data = await storage.download_file(media_file.storage_path)
            
            # Create temporary file
            temp_input = self.temp_dir / f"input_{media_file.id}.tmp"
            with open(temp_input, "wb") as f:
                f.write(file_data)
            
            try:
                # Extract metadata using FFmpeg
                metadata = await self._extract_audio_metadata(str(temp_input))
                
                # Update media file with metadata
                if metadata:
                    media_file.duration = metadata.get("duration", media_file.duration)
                    media_file.bitrate = metadata.get("bitrate", media_file.bitrate)
                    
                    # Merge metadata
                    if media_file.metadata:
                        media_file.metadata.update(metadata)
                    else:
                        media_file.metadata = metadata
                
                # Generate waveform thumbnail if enabled
                if self.settings.GENERATE_AUDIO_WAVEFORMS:
                    waveform_data = await self._generate_audio_waveform(str(temp_input))
                    if waveform_data:
                        waveform_filename = f"waveform_{media_file.filename}.png"
                        waveform_result = await storage.upload_file(
                            file_data=waveform_data,
                            filename=waveform_filename,
                            user_id=str(media_file.uploaded_by) if media_file.uploaded_by else None
                        )
                        media_file.thumbnail_path = waveform_result["storage_path"]
                
            finally:
                # Clean up temporary file
                if temp_input.exists():
                    temp_input.unlink()
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error("Audio processing failed", file_id=str(media_file.id), error=str(e))
            return False
    
    async def _process_document(self, media_file: MediaFile, db: AsyncSession) -> bool:
        """Process document file - extract metadata and generate preview."""
        try:
            # For now, just extract basic metadata
            metadata_extractor = get_metadata_extractor()
            storage = get_storage()
            
            # Download file for metadata extraction
            file_data = await storage.download_file(media_file.storage_path)
            metadata = await metadata_extractor.extract_document_metadata(file_data, media_file.original_filename)
            
            # Update metadata
            if metadata:
                if media_file.metadata:
                    media_file.metadata.update(metadata)
                else:
                    media_file.metadata = metadata
            
            await db.commit()
            return True
            
        except Exception as e:
            logger.error("Document processing failed", file_id=str(media_file.id), error=str(e))
            return False
    
    async def _generate_image_thumbnail(self, image: Image.Image, size: Tuple[int, int] = (300, 300)) -> Optional[bytes]:
        """Generate thumbnail for image."""
        try:
            # Create thumbnail
            thumbnail = image.copy()
            thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if thumbnail.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', thumbnail.size, (255, 255, 255))
                if thumbnail.mode == 'P':
                    thumbnail = thumbnail.convert('RGBA')
                background.paste(thumbnail, mask=thumbnail.split()[-1] if thumbnail.mode == 'RGBA' else None)
                thumbnail = background
            
            # Save to bytes
            output = BytesIO()
            thumbnail.save(output, format='JPEG', quality=85, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error("Failed to generate image thumbnail", error=str(e))
            return None
    
    async def _generate_video_thumbnail(self, input_path: str, time_offset: float = 1.0) -> Optional[bytes]:
        """Generate thumbnail from video at specified time offset."""
        try:
            temp_output = self.temp_dir / f"thumb_{uuid.uuid4()}.jpg"
            
            # Use FFmpeg to extract frame
            (
                ffmpeg
                .input(input_path, ss=time_offset)
                .output(str(temp_output), vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Read generated thumbnail
            if temp_output.exists():
                with open(temp_output, 'rb') as f:
                    thumbnail_data = f.read()
                temp_output.unlink()
                return thumbnail_data
            
            return None
            
        except Exception as e:
            logger.error("Failed to generate video thumbnail", error=str(e))
            return None
    
    async def _generate_video_preview(self, input_path: str, preset: str = "web_medium") -> Optional[bytes]:
        """Generate web-optimized video preview."""
        try:
            temp_output = self.temp_dir / f"preview_{uuid.uuid4()}.mp4"
            preset_config = self.video_presets.get(preset, self.video_presets["web_medium"])
            
            # Build FFmpeg command
            stream = ffmpeg.input(input_path)
            
            # Apply video filters
            video = stream.video.filter('scale', preset_config["resolution"])
            audio = stream.audio
            
            # Output with specified codec and bitrate
            out = ffmpeg.output(
                video, audio, str(temp_output),
                vcodec=preset_config["video_codec"],
                acodec=preset_config["audio_codec"],
                video_bitrate=preset_config["video_bitrate"],
                audio_bitrate=preset_config["audio_bitrate"],
                r=preset_config["fps"]
            )
            
            ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
            # Read generated preview
            if temp_output.exists():
                with open(temp_output, 'rb') as f:
                    preview_data = f.read()
                temp_output.unlink()
                return preview_data
            
            return None
            
        except Exception as e:
            logger.error("Failed to generate video preview", error=str(e))
            return None
    
    async def _generate_audio_waveform(self, input_path: str) -> Optional[bytes]:
        """Generate waveform visualization for audio file."""
        try:
            temp_output = self.temp_dir / f"waveform_{uuid.uuid4()}.png"
            
            # Use FFmpeg to generate waveform
            (
                ffmpeg
                .input(input_path)
                .output(
                    str(temp_output),
                    filter_complex='[0:a]showwavespic=s=600x200:colors=0x3498db',
                    frames=1
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Read generated waveform
            if temp_output.exists():
                with open(temp_output, 'rb') as f:
                    waveform_data = f.read()
                temp_output.unlink()
                return waveform_data
            
            return None
            
        except Exception as e:
            logger.error("Failed to generate audio waveform", error=str(e))
            return None
    
    async def _extract_video_metadata(self, input_path: str) -> Dict[str, Any]:
        """Extract metadata from video file using FFmpeg."""
        try:
            probe = ffmpeg.probe(input_path)
            
            metadata = {}
            
            # Get format information
            format_info = probe.get('format', {})
            metadata['duration'] = float(format_info.get('duration', 0))
            metadata['bitrate'] = int(format_info.get('bit_rate', 0))
            metadata['format_name'] = format_info.get('format_name')
            metadata['size'] = int(format_info.get('size', 0))
            
            # Get video stream information
            video_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'video']
            if video_streams:
                video_stream = video_streams[0]
                metadata['width'] = int(video_stream.get('width', 0))
                metadata['height'] = int(video_stream.get('height', 0))
                metadata['video_codec'] = video_stream.get('codec_name')
                
                # Calculate frame rate
                r_frame_rate = video_stream.get('r_frame_rate', '0/1')
                if '/' in r_frame_rate:
                    num, den = map(int, r_frame_rate.split('/'))
                    if den > 0:
                        metadata['frame_rate'] = num / den
            
            # Get audio stream information
            audio_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']
            if audio_streams:
                audio_stream = audio_streams[0]
                metadata['audio_codec'] = audio_stream.get('codec_name')
                metadata['sample_rate'] = int(audio_stream.get('sample_rate', 0))
                metadata['channels'] = int(audio_stream.get('channels', 0))
            
            return metadata
            
        except Exception as e:
            logger.error("Failed to extract video metadata", error=str(e))
            return {}
    
    async def _extract_audio_metadata(self, input_path: str) -> Dict[str, Any]:
        """Extract metadata from audio file using FFmpeg."""
        try:
            probe = ffmpeg.probe(input_path)
            
            metadata = {}
            
            # Get format information
            format_info = probe.get('format', {})
            metadata['duration'] = float(format_info.get('duration', 0))
            metadata['bitrate'] = int(format_info.get('bit_rate', 0))
            metadata['format_name'] = format_info.get('format_name')
            
            # Get audio stream information
            audio_streams = [s for s in probe.get('streams', []) if s.get('codec_type') == 'audio']
            if audio_streams:
                audio_stream = audio_streams[0]
                metadata['audio_codec'] = audio_stream.get('codec_name')
                metadata['sample_rate'] = int(audio_stream.get('sample_rate', 0))
                metadata['channels'] = int(audio_stream.get('channels', 0))
            
            # Extract tags if available
            tags = format_info.get('tags', {})
            if tags:
                metadata['tags'] = {
                    'title': tags.get('title'),
                    'artist': tags.get('artist'),
                    'album': tags.get('album'),
                    'date': tags.get('date'),
                    'genre': tags.get('genre')
                }
            
            return metadata
            
        except Exception as e:
            logger.error("Failed to extract audio metadata", error=str(e))
            return {}
    
    async def create_processing_job(
        self,
        media_file_id: uuid.UUID,
        job_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        priority: int = 5
    ) -> uuid.UUID:
        """Create a processing job for a media file."""
        try:
            async for db in get_db():
                job = ProcessingJob(
                    media_file_id=media_file_id,
                    job_type=job_type,
                    status="pending",
                    priority=priority,
                    input_parameters=parameters or {}
                )
                
                db.add(job)
                await db.commit()
                
                logger.info(
                    "Processing job created",
                    job_id=str(job.id),
                    media_file_id=str(media_file_id),
                    job_type=job_type
                )
                
                return job.id
                
        except Exception as e:
            logger.error("Failed to create processing job", error=str(e))
            raise


# Global media processor instance
media_processor = MediaProcessor()


def get_media_processor() -> MediaProcessor:
    """Get media processor instance."""
    return media_processor