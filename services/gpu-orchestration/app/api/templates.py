#!/usr/bin/env python3
"""
Templates API endpoints for the AIMA GPU Orchestration Service.

This module provides REST API endpoints for job template management.
"""

import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.job_manager import JobManager
from ..models.gpu_models import JobType


logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for API
class JobTemplateRequest(BaseModel):
    """Request model for creating job templates."""
    name: str = Field(..., description="Template name")
    job_type: JobType = Field(..., description="Type of job")
    model_name: str = Field(..., description="Model name")
    default_config: Dict[str, Any] = Field(..., description="Default configuration")
    resource_requirements: Dict[str, Any] = Field(..., description="Resource requirements")
    description: Optional[str] = Field(None, description="Template description")


class JobTemplateResponse(BaseModel):
    """Response model for job templates."""
    id: str
    name: str
    job_type: str
    model_name: str
    default_config: Dict[str, Any]
    resource_requirements: Dict[str, Any]
    description: Optional[str] = None
    created_at: str
    updated_at: str
    usage_count: int = 0


class JobTemplateListResponse(BaseModel):
    """Response model for template list."""
    templates: List[JobTemplateResponse]
    total_count: int


# Dependency to get user ID (simplified for now)
def get_current_user_id() -> str:
    """Get current user ID. In production, this would extract from JWT token."""
    # TODO: Implement proper authentication
    return "user123"


@router.post("/", response_model=JobTemplateResponse)
async def create_job_template(
    request: JobTemplateRequest,
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Create a new job template."""
    try:
        logger.info(
            "Creating job template",
            template_name=request.name,
            job_type=request.job_type.value,
            user_id=user_id
        )
        
        template = await job_manager.create_job_template(
            db=db,
            name=request.name,
            job_type=request.job_type,
            model_name=request.model_name,
            default_config=request.default_config,
            resource_requirements=request.resource_requirements,
            description=request.description
        )
        
        return JobTemplateResponse(
            id=str(template.id),
            name=template.name,
            job_type=template.job_type,
            model_name=template.model_name,
            default_config=template.default_config,
            resource_requirements=template.resource_requirements,
            description=template.description,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
            usage_count=0  # TODO: Calculate actual usage
        )
        
    except ValueError as e:
        logger.warning(f"Invalid template creation request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating job template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job template")


@router.get("/", response_model=JobTemplateListResponse)
async def list_job_templates(
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends()
):
    """List all available job templates."""
    try:
        logger.info("Listing job templates", job_type=job_type.value if job_type else None)
        
        templates = await job_manager.list_job_templates(db)
        
        # Filter by job type if specified
        if job_type:
            templates = [t for t in templates if t.job_type == job_type.value]
        
        template_responses = [
            JobTemplateResponse(
                id=str(template.id),
                name=template.name,
                job_type=template.job_type,
                model_name=template.model_name,
                default_config=template.default_config,
                resource_requirements=template.resource_requirements,
                description=template.description,
                created_at=template.created_at.isoformat(),
                updated_at=template.updated_at.isoformat(),
                usage_count=0  # TODO: Calculate actual usage
            )
            for template in templates
        ]
        
        return JobTemplateListResponse(
            templates=template_responses,
            total_count=len(template_responses)
        )
        
    except Exception as e:
        logger.error(f"Error listing job templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to list job templates")


@router.get("/{template_name}", response_model=JobTemplateResponse)
async def get_job_template(
    template_name: str = Path(..., description="Template name"),
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends()
):
    """Get a specific job template by name."""
    try:
        logger.info("Getting job template", template_name=template_name)
        
        template = await job_manager.get_job_template(db, template_name)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        return JobTemplateResponse(
            id=str(template.id),
            name=template.name,
            job_type=template.job_type,
            model_name=template.model_name,
            default_config=template.default_config,
            resource_requirements=template.resource_requirements,
            description=template.description,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
            usage_count=0  # TODO: Calculate actual usage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job template {template_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job template")


@router.put("/{template_name}", response_model=JobTemplateResponse)
async def update_job_template(
    template_name: str = Path(..., description="Template name"),
    request: JobTemplateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Update an existing job template."""
    try:
        logger.info("Updating job template", template_name=template_name, user_id=user_id)
        
        # Get existing template
        template = await job_manager.get_job_template(db, template_name)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        # Update template fields
        template.name = request.name
        template.job_type = request.job_type.value
        template.model_name = request.model_name
        template.default_config = request.default_config
        template.resource_requirements = request.resource_requirements
        template.description = request.description
        
        await db.commit()
        await db.refresh(template)
        
        return JobTemplateResponse(
            id=str(template.id),
            name=template.name,
            job_type=template.job_type,
            model_name=template.model_name,
            default_config=template.default_config,
            resource_requirements=template.resource_requirements,
            description=template.description,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
            usage_count=0  # TODO: Calculate actual usage
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid template update request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating job template {template_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update job template")


@router.delete("/{template_name}")
async def delete_job_template(
    template_name: str = Path(..., description="Template name"),
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Delete a job template."""
    try:
        logger.info("Deleting job template", template_name=template_name, user_id=user_id)
        
        # Get existing template
        template = await job_manager.get_job_template(db, template_name)
        
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
        
        # TODO: Check if template is in use by active jobs
        
        # Delete template
        await db.delete(template)
        await db.commit()
        
        return {"message": f"Template '{template_name}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job template {template_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete job template")


@router.get("/presets/llava")
async def get_llava_presets():
    """Get predefined LLaVA job templates."""
    return {
        "presets": [
            {
                "name": "llava-1.6-34b-inference",
                "job_type": "llava_inference",
                "model_name": "llava-1.6-34b",
                "description": "LLaVA-1.6 34B multimodal inference",
                "default_config": {
                    "max_tokens": 2048,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "batch_size": 1
                },
                "resource_requirements": {
                    "gpu_type": "RTX4090",
                    "gpu_count": 4,
                    "memory_gb": 96,
                    "cpu_cores": 16,
                    "ram_gb": 64
                },
                "estimated_cost_per_hour": 3.56
            },
            {
                "name": "llava-1.6-13b-inference",
                "job_type": "llava_inference",
                "model_name": "llava-1.6-13b",
                "description": "LLaVA-1.6 13B multimodal inference (cost-optimized)",
                "default_config": {
                    "max_tokens": 2048,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "batch_size": 2
                },
                "resource_requirements": {
                    "gpu_type": "RTX4090",
                    "gpu_count": 2,
                    "memory_gb": 48,
                    "cpu_cores": 8,
                    "ram_gb": 32
                },
                "estimated_cost_per_hour": 1.78
            }
        ]
    }


@router.get("/presets/llama")
async def get_llama_presets():
    """Get predefined Llama job templates."""
    return {
        "presets": [
            {
                "name": "llama-3.1-70b-inference",
                "job_type": "llama_inference",
                "model_name": "llama-3.1-70b",
                "description": "Llama 3.1 70B text generation",
                "default_config": {
                    "max_tokens": 4096,
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "batch_size": 1
                },
                "resource_requirements": {
                    "gpu_type": "RTX4090",
                    "gpu_count": 2,
                    "memory_gb": 48,
                    "cpu_cores": 8,
                    "ram_gb": 32
                },
                "estimated_cost_per_hour": 1.78
            },
            {
                "name": "llama-3.1-8b-inference",
                "job_type": "llama_inference",
                "model_name": "llama-3.1-8b",
                "description": "Llama 3.1 8B text generation (fast)",
                "default_config": {
                    "max_tokens": 4096,
                    "temperature": 0.8,
                    "top_p": 0.95,
                    "batch_size": 4
                },
                "resource_requirements": {
                    "gpu_type": "RTX4090",
                    "gpu_count": 1,
                    "memory_gb": 24,
                    "cpu_cores": 4,
                    "ram_gb": 16
                },
                "estimated_cost_per_hour": 0.89
            }
        ]
    }


@router.post("/presets/{preset_name}/create")
async def create_template_from_preset(
    preset_name: str = Path(..., description="Preset name"),
    template_name: str = Body(..., embed=True, description="New template name"),
    db: AsyncSession = Depends(get_db),
    job_manager: JobManager = Depends(),
    user_id: str = Depends(get_current_user_id)
):
    """Create a job template from a preset."""
    try:
        logger.info(
            "Creating template from preset",
            preset_name=preset_name,
            template_name=template_name,
            user_id=user_id
        )
        
        # Get preset data
        llava_presets = (await get_llava_presets())["presets"]
        llama_presets = (await get_llama_presets())["presets"]
        all_presets = llava_presets + llama_presets
        
        preset = next((p for p in all_presets if p["name"] == preset_name), None)
        
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' not found")
        
        # Create template from preset
        template = await job_manager.create_job_template(
            db=db,
            name=template_name,
            job_type=JobType(preset["job_type"]),
            model_name=preset["model_name"],
            default_config=preset["default_config"],
            resource_requirements=preset["resource_requirements"],
            description=f"Created from preset: {preset['description']}"
        )
        
        return JobTemplateResponse(
            id=str(template.id),
            name=template.name,
            job_type=template.job_type,
            model_name=template.model_name,
            default_config=template.default_config,
            resource_requirements=template.resource_requirements,
            description=template.description,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
            usage_count=0
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid preset template creation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating template from preset: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template from preset")