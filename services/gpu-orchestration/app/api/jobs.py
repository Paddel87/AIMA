#!/usr/bin/env python3
"""
Jobs API endpoints for the AIMA GPU Orchestration Service.

This module provides REST API endpoints for job management operations.
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.gpu_orchestrator import GPUOrchestrator
from ..services.job_manager import JobManager, JobPriority
from ..models.gpu_models import JobType, JobStatus


logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for API
class JobSubmissionRequest(BaseModel):
    """Request model for job submission."""
    job_type: JobType = Field(..., description="Type of job to execute")
    model_name: str = Field(..., description="Name of the model to use")
    input_data: Dict[str, Any] = Field(..., description="Input data for the job")
    priority: int = Field(default=JobPriority.NORMAL, ge=1, le=10, description="Job priority (1=highest, 10=lowest)")
    max_runtime_minutes: int = Field(default=60, ge=1, le=1440, description="Maximum runtime in minutes")
    template_name: Optional[str] = Field(None, description="Optional job template to use")
    config_overrides: Optional[Dict[str, Any]] = Field(None, description="Configuration overrides")


class JobResponse(BaseModel):
    """Response model for job information."""
    job_id: str
    status: JobStatus
    job_type: str
    model_name: str
    priority: int
    progress_percentage: float
    created_at: str
    estimated_cost_usd: Optional[float]
    actual_cost_usd: Optional[float]
    assigned_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    estimated_completion_at: Optional[str] = None
    instance: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    """Response model for job list."""
    jobs: List[JobResponse]
    total_count: int
    page: int
    page_size: int


class PriorityUpdateRequest(BaseModel):
    """Request model for updating job priority."""
    priority: int = Field(..., ge=1, le=10, description="New priority (1=highest, 10=lowest)")


class QuotaStatusResponse(BaseModel):
    """Response model for user quota status."""
    user_id: str
    max_concurrent_jobs: int
    max_gpu_hours_per_day: float
    max_cost_per_day_usd: float
    current_concurrent_jobs: int
    gpu_hours_used_today: float
    cost_used_today_usd: float
    quota_exceeded: bool


# Dependency to get user ID (simplified for now)
def get_current_user_id() -> str:
    """Get current user ID. In production, this would extract from JWT token."""
    # TODO: Implement proper authentication
    return "user123"


@router.post("/submit", response_model=JobResponse)
async def submit_job(
    request: JobSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    orchestrator: GPUOrchestrator = Depends(),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Submit a new GPU job for processing."""
    try:
        logger.info(
            "Submitting job",
            user_id=user_id,
            job_type=request.job_type.value,
            model_name=request.model_name
        )
        
        # Submit job using template if specified
        if request.template_name:
            job = await job_manager.submit_job_from_template(
                db=db,
                user_id=user_id,
                template_name=request.template_name,
                input_data=request.input_data,
                priority=request.priority,
                config_overrides=request.config_overrides,
                max_runtime_minutes=request.max_runtime_minutes
            )
        else:
            # Submit job directly
            job = await orchestrator.submit_job(
                db=db,
                user_id=user_id,
                job_type=request.job_type,
                model_name=request.model_name,
                input_data=request.input_data,
                priority=request.priority,
                max_runtime_minutes=request.max_runtime_minutes
            )
        
        # Get job status for response
        job_status = await orchestrator.get_job_status(db, str(job.id), user_id)
        
        if not job_status:
            raise HTTPException(status_code=500, detail="Failed to retrieve job status")
        
        return JobResponse(**job_status)
        
    except ValueError as e:
        logger.warning(f"Invalid job submission: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit job")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str = Path(..., description="Job ID"),
    db: AsyncSession = Depends(get_db),
    orchestrator: GPUOrchestrator = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Get status and details of a specific job."""
    try:
        job_status = await orchestrator.get_job_status(db, job_id, user_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobResponse(**job_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of jobs per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    db: AsyncSession = Depends(get_db),
    orchestrator: GPUOrchestrator = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """List jobs for the current user."""
    try:
        offset = (page - 1) * page_size
        
        jobs = await orchestrator.list_user_jobs(
            db=db,
            user_id=user_id,
            limit=page_size,
            offset=offset,
            status_filter=status
        )
        
        # Convert to response format
        job_responses = [JobResponse(**job) for job in jobs]
        
        return JobListResponse(
            jobs=job_responses,
            total_count=len(job_responses),  # TODO: Get actual total count
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Error listing jobs for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list jobs")


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str = Path(..., description="Job ID"),
    db: AsyncSession = Depends(get_db),
    orchestrator: GPUOrchestrator = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Cancel a running or queued job."""
    try:
        success = await orchestrator.cancel_job(db, job_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or cannot be cancelled")
        
        return {"message": "Job cancelled successfully", "job_id": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.put("/{job_id}/priority", response_model=JobResponse)
async def update_job_priority(
    job_id: str = Path(..., description="Job ID"),
    request: PriorityUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    orchestrator: GPUOrchestrator = Depends(),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Update the priority of a queued job."""
    try:
        success = await job_manager.update_job_priority(
            db=db,
            job_id=job_id,
            user_id=user_id,
            new_priority=request.priority
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or cannot update priority (job may not be queued)"
            )
        
        # Get updated job status
        job_status = await orchestrator.get_job_status(db, job_id, user_id)
        
        if not job_status:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated job status")
        
        return JobResponse(**job_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job priority {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update job priority")


@router.get("/queue/status")
async def get_queue_status(
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends()
):
    """Get current queue status and metrics."""
    try:
        queue_status = await job_manager.get_queue_status(db)
        return queue_status
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue status")


@router.get("/quota/status", response_model=QuotaStatusResponse)
async def get_quota_status(
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Get current user's quota status and usage."""
    try:
        quota_status = await job_manager.get_user_quota_status(db, user_id)
        
        if not quota_status:
            raise HTTPException(status_code=500, detail="Failed to retrieve quota status")
        
        return QuotaStatusResponse(**quota_status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quota status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quota status")


@router.get("/types")
async def get_job_types():
    """Get available job types."""
    return {
        "job_types": [
            {
                "name": job_type.value,
                "description": {
                    JobType.LLAVA_INFERENCE: "LLaVA multimodal inference",
                    JobType.LLAMA_INFERENCE: "Llama text generation",
                    JobType.TRAINING: "Model training",
                    JobType.BATCH_PROCESSING: "Batch processing"
                }.get(job_type, "Unknown job type")
            }
            for job_type in JobType
        ]
    }


@router.get("/priorities")
async def get_priority_levels():
    """Get available priority levels."""
    return {
        "priority_levels": [
            {"level": JobPriority.CRITICAL, "name": "Critical", "description": "Highest priority"},
            {"level": JobPriority.HIGH, "name": "High", "description": "High priority"},
            {"level": JobPriority.NORMAL, "name": "Normal", "description": "Normal priority"},
            {"level": JobPriority.LOW, "name": "Low", "description": "Low priority"},
            {"level": JobPriority.BACKGROUND, "name": "Background", "description": "Lowest priority"}
        ]
    }