#!/usr/bin/env python3
"""
GPU Orchestrator Service for the AIMA GPU Orchestration Service.

This module implements the core orchestration logic for managing GPU resources,
job scheduling, and provider selection.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from ..models.gpu_models import (
    GPUInstance, GPUJob, ProviderConfig, JobTemplate, ResourceQuota,
    InstanceStatus, JobStatus, JobType, GPUType, GPUProvider
)
from ..providers.base_provider import BaseGPUProvider, ProviderError
from ..providers.runpod_provider import RunPodProvider
from ..core.config import get_settings


logger = logging.getLogger(__name__)


class SchedulingStrategy(str, Enum):
    """Job scheduling strategies."""
    COST_OPTIMIZED = "cost_optimized"
    PERFORMANCE_OPTIMIZED = "performance_optimized"
    BALANCED = "balanced"
    FASTEST_AVAILABLE = "fastest_available"


class GPUOrchestrator:
    """Main GPU orchestration service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.providers: Dict[str, BaseGPUProvider] = {}
        self.scheduling_strategy = SchedulingStrategy.BALANCED
        
        # Initialize providers
        self._initialize_providers()
        
        # Orchestration settings
        self.max_concurrent_jobs = self.settings.MAX_CONCURRENT_JOBS
        self.job_timeout_hours = self.settings.JOB_TIMEOUT_HOURS
        self.max_retry_attempts = 3
        
        # Cost optimization settings
        self.cost_optimization_enabled = self.settings.COST_OPTIMIZATION_ENABLED
        self.max_hourly_cost = self.settings.MAX_HOURLY_COST_USD
        
        # Monitoring
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._instance_monitors: Dict[str, asyncio.Task] = {}
    
    def _initialize_providers(self):
        """Initialize available GPU providers."""
        try:
            # Initialize RunPod provider
            if self.settings.RUNPOD_API_KEY:
                self.providers["runpod"] = RunPodProvider()
                logger.info("RunPod provider initialized")
            
            # TODO: Initialize other providers (Vast.ai, AWS, etc.)
            # if self.settings.VAST_API_KEY:
            #     self.providers["vast"] = VastProvider()
            
            if not self.providers:
                logger.warning("No GPU providers configured")
            else:
                logger.info(f"Initialized {len(self.providers)} GPU providers: {list(self.providers.keys())}")
                
        except Exception as e:
            logger.error("Error initializing GPU providers", error=str(e))
    
    async def submit_job(
        self,
        db: AsyncSession,
        user_id: str,
        job_type: JobType,
        model_name: str,
        input_data: Dict[str, Any],
        priority: int = 5,
        **kwargs
    ) -> GPUJob:
        """Submit a new GPU job for processing."""
        try:
            logger.info(
                "Submitting new GPU job",
                user_id=user_id,
                job_type=job_type.value,
                model_name=model_name,
                priority=priority
            )
            
            # Check user quota
            await self._check_user_quota(db, user_id)
            
            # Determine resource requirements
            resource_requirements = await self._determine_resource_requirements(
                job_type, model_name, input_data
            )
            
            # Estimate cost
            estimated_cost = await self._estimate_job_cost(
                job_type, resource_requirements, kwargs.get("max_runtime_minutes", 60)
            )
            
            # Create job record
            job = GPUJob(
                user_id=user_id,
                job_type=job_type.value,
                model_name=model_name,
                priority=priority,
                required_gpu_type=resource_requirements["gpu_type"],
                required_gpu_count=resource_requirements["gpu_count"],
                required_memory_gb=resource_requirements["memory_gb"],
                max_runtime_minutes=kwargs.get("max_runtime_minutes", 60),
                input_data=input_data,
                estimated_cost_usd=estimated_cost,
                status=JobStatus.QUEUED
            )
            
            db.add(job)
            await db.commit()
            await db.refresh(job)
            
            # Start job processing
            task = asyncio.create_task(self._process_job(db, job))
            self._running_jobs[str(job.id)] = task
            
            logger.info(
                "GPU job submitted successfully",
                job_id=str(job.id),
                estimated_cost=estimated_cost
            )
            
            return job
            
        except Exception as e:
            logger.error("Error submitting GPU job", error=str(e), user_id=user_id)
            raise
    
    async def cancel_job(self, db: AsyncSession, job_id: str, user_id: str) -> bool:
        """Cancel a running or queued job."""
        try:
            # Get job
            result = await db.execute(
                select(GPUJob)
                .where(and_(GPUJob.id == job_id, GPUJob.user_id == user_id))
                .options(selectinload(GPUJob.instance))
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.warning("Job not found for cancellation", job_id=job_id, user_id=user_id)
                return False
            
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                logger.warning("Job already finished", job_id=job_id, status=job.status)
                return False
            
            logger.info("Cancelling GPU job", job_id=job_id, status=job.status)
            
            # Cancel running task
            if job_id in self._running_jobs:
                self._running_jobs[job_id].cancel()
                del self._running_jobs[job_id]
            
            # Terminate instance if assigned
            if job.instance:
                provider = self.providers.get(job.instance.provider)
                if provider:
                    await provider.terminate_instance(db, job.instance)
            
            # Update job status
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            
            await db.commit()
            
            logger.info("GPU job cancelled successfully", job_id=job_id)
            return True
            
        except Exception as e:
            logger.error("Error cancelling GPU job", error=str(e), job_id=job_id)
            return False
    
    async def get_job_status(self, db: AsyncSession, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get status and details of a job."""
        try:
            result = await db.execute(
                select(GPUJob)
                .where(and_(GPUJob.id == job_id, GPUJob.user_id == user_id))
                .options(selectinload(GPUJob.instance))
            )
            job = result.scalar_one_or_none()
            
            if not job:
                return None
            
            status_data = {
                "job_id": str(job.id),
                "status": job.status,
                "job_type": job.job_type,
                "model_name": job.model_name,
                "priority": job.priority,
                "progress_percentage": job.progress_percentage,
                "created_at": job.created_at.isoformat(),
                "estimated_cost_usd": job.estimated_cost_usd,
                "actual_cost_usd": job.actual_cost_usd
            }
            
            if job.assigned_at:
                status_data["assigned_at"] = job.assigned_at.isoformat()
            if job.started_at:
                status_data["started_at"] = job.started_at.isoformat()
            if job.completed_at:
                status_data["completed_at"] = job.completed_at.isoformat()
            if job.estimated_completion_at:
                status_data["estimated_completion_at"] = job.estimated_completion_at.isoformat()
            
            if job.instance:
                status_data["instance"] = {
                    "id": str(job.instance.id),
                    "provider": job.instance.provider,
                    "gpu_type": job.instance.gpu_type,
                    "gpu_count": job.instance.gpu_count,
                    "status": job.instance.status,
                    "public_ip": job.instance.public_ip
                }
            
            if job.output_data:
                status_data["output_data"] = job.output_data
            
            if job.error_message:
                status_data["error_message"] = job.error_message
            
            return status_data
            
        except Exception as e:
            logger.error("Error getting job status", error=str(e), job_id=job_id)
            return None
    
    async def list_user_jobs(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[JobStatus] = None
    ) -> List[Dict[str, Any]]:
        """List jobs for a user."""
        try:
            query = select(GPUJob).where(GPUJob.user_id == user_id)
            
            if status_filter:
                query = query.where(GPUJob.status == status_filter)
            
            query = query.order_by(GPUJob.created_at.desc()).limit(limit).offset(offset)
            
            result = await db.execute(query)
            jobs = result.scalars().all()
            
            job_list = []
            for job in jobs:
                job_data = {
                    "job_id": str(job.id),
                    "status": job.status,
                    "job_type": job.job_type,
                    "model_name": job.model_name,
                    "priority": job.priority,
                    "progress_percentage": job.progress_percentage,
                    "created_at": job.created_at.isoformat(),
                    "estimated_cost_usd": job.estimated_cost_usd,
                    "actual_cost_usd": job.actual_cost_usd
                }
                
                if job.completed_at:
                    job_data["completed_at"] = job.completed_at.isoformat()
                
                job_list.append(job_data)
            
            return job_list
            
        except Exception as e:
            logger.error("Error listing user jobs", error=str(e), user_id=user_id)
            return []
    
    async def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all GPU providers."""
        provider_status = {}
        
        for provider_name, provider in self.providers.items():
            try:
                health_check = await provider.health_check()
                provider_status[provider_name] = health_check
            except Exception as e:
                provider_status[provider_name] = {
                    "provider": provider_name,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return provider_status
    
    async def _process_job(self, db: AsyncSession, job: GPUJob):
        """Process a GPU job through its lifecycle."""
        try:
            logger.info("Starting job processing", job_id=str(job.id))
            
            # Find best provider and create instance
            provider, instance = await self._assign_job_to_instance(db, job)
            
            if not provider or not instance:
                await self._fail_job(db, job, "No suitable GPU instance available")
                return
            
            # Update job status
            job.status = JobStatus.ASSIGNED
            job.assigned_at = datetime.utcnow()
            job.instance_id = instance.id
            await db.commit()
            
            # Wait for instance to be ready
            await self._wait_for_instance_ready(db, instance)
            
            # Start job execution
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            job.estimated_completion_at = datetime.utcnow() + timedelta(minutes=job.max_runtime_minutes)
            await db.commit()
            
            # Execute job
            success = await self._execute_job_on_instance(db, job, instance, provider)
            
            if success:
                job.status = JobStatus.COMPLETED
                job.progress_percentage = 100.0
            else:
                job.status = JobStatus.FAILED
                job.error_message = "Job execution failed"
            
            job.completed_at = datetime.utcnow()
            
            # Calculate actual cost
            if job.started_at and job.completed_at:
                runtime_hours = (job.completed_at - job.started_at).total_seconds() / 3600
                job.actual_cost_usd = runtime_hours * instance.hourly_cost_usd
            
            await db.commit()
            
            # Cleanup instance
            await provider.terminate_instance(db, instance)
            
            logger.info(
                "Job processing completed",
                job_id=str(job.id),
                status=job.status,
                actual_cost=job.actual_cost_usd
            )
            
        except Exception as e:
            logger.error("Error processing job", error=str(e), job_id=str(job.id))
            await self._fail_job(db, job, f"Processing error: {str(e)}")
        
        finally:
            # Cleanup
            if str(job.id) in self._running_jobs:
                del self._running_jobs[str(job.id)]
    
    async def _assign_job_to_instance(
        self,
        db: AsyncSession,
        job: GPUJob
    ) -> Tuple[Optional[BaseGPUProvider], Optional[GPUInstance]]:
        """Assign job to the best available GPU instance."""
        try:
            # Get resource requirements
            gpu_type = GPUType(job.required_gpu_type)
            gpu_count = job.required_gpu_count
            
            # Find best provider
            best_provider = await self._select_best_provider(job, gpu_type, gpu_count)
            
            if not best_provider:
                logger.warning("No suitable provider found", job_id=str(job.id))
                return None, None
            
            # Create instance
            instance = await best_provider.create_instance(
                db, job, gpu_type, gpu_count
            )
            
            logger.info(
                "Job assigned to instance",
                job_id=str(job.id),
                instance_id=str(instance.id),
                provider=best_provider.provider_name
            )
            
            return best_provider, instance
            
        except Exception as e:
            logger.error("Error assigning job to instance", error=str(e), job_id=str(job.id))
            return None, None
    
    async def _select_best_provider(
        self,
        job: GPUJob,
        gpu_type: GPUType,
        gpu_count: int
    ) -> Optional[BaseGPUProvider]:
        """Select the best provider for a job based on strategy."""
        suitable_providers = []
        
        for provider_name, provider in self.providers.items():
            try:
                # Validate requirements
                is_valid, error = await provider.validate_job_requirements(
                    job, gpu_type, gpu_count
                )
                
                if is_valid:
                    # Get cost estimate
                    cost = await provider.estimate_cost(
                        gpu_type, gpu_count, job.max_runtime_minutes
                    )
                    
                    suitable_providers.append({
                        "provider": provider,
                        "cost": cost,
                        "name": provider_name
                    })
                    
            except Exception as e:
                logger.warning(
                    f"Error evaluating provider {provider_name}",
                    error=str(e)
                )
        
        if not suitable_providers:
            return None
        
        # Select based on strategy
        if self.scheduling_strategy == SchedulingStrategy.COST_OPTIMIZED:
            best = min(suitable_providers, key=lambda p: p["cost"])
        elif self.scheduling_strategy == SchedulingStrategy.FASTEST_AVAILABLE:
            # For now, just pick the first available
            best = suitable_providers[0]
        else:  # BALANCED or default
            # Balance cost and availability
            best = min(suitable_providers, key=lambda p: p["cost"])
        
        logger.info(
            "Selected provider",
            provider=best["name"],
            cost=best["cost"],
            strategy=self.scheduling_strategy
        )
        
        return best["provider"]
    
    async def _wait_for_instance_ready(
        self,
        db: AsyncSession,
        instance: GPUInstance,
        timeout_minutes: int = 10
    ):
        """Wait for instance to be ready."""
        start_time = datetime.utcnow()
        timeout = timedelta(minutes=timeout_minutes)
        
        while datetime.utcnow() - start_time < timeout:
            await db.refresh(instance)
            
            if instance.status == InstanceStatus.RUNNING:
                logger.info("Instance is ready", instance_id=str(instance.id))
                return
            elif instance.status in [InstanceStatus.FAILED, InstanceStatus.TERMINATED]:
                raise ProviderError(f"Instance failed to start: {instance.status}")
            
            await asyncio.sleep(10)  # Check every 10 seconds
        
        raise ProviderError("Instance startup timeout")
    
    async def _execute_job_on_instance(
        self,
        db: AsyncSession,
        job: GPUJob,
        instance: GPUInstance,
        provider: BaseGPUProvider
    ) -> bool:
        """Execute job on the assigned instance."""
        try:
            # This is a simplified implementation
            # In practice, this would involve:
            # 1. Uploading input data to instance
            # 2. Starting the model inference/training
            # 3. Monitoring progress
            # 4. Downloading results
            
            logger.info(
                "Executing job on instance",
                job_id=str(job.id),
                instance_id=str(instance.id)
            )
            
            # Simulate job execution
            await asyncio.sleep(5)  # Placeholder for actual execution
            
            # Update progress
            job.progress_percentage = 100.0
            job.output_data = {
                "status": "completed",
                "result": "Job executed successfully",
                "execution_time": 5.0
            }
            
            await db.commit()
            
            return True
            
        except Exception as e:
            logger.error(
                "Error executing job on instance",
                error=str(e),
                job_id=str(job.id),
                instance_id=str(instance.id)
            )
            return False
    
    async def _fail_job(self, db: AsyncSession, job: GPUJob, error_message: str):
        """Mark job as failed."""
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.utcnow()
        await db.commit()
        
        logger.error("Job failed", job_id=str(job.id), error=error_message)
    
    async def _check_user_quota(self, db: AsyncSession, user_id: str):
        """Check if user has sufficient quota."""
        # Implementation would check ResourceQuota table
        # For now, just a placeholder
        pass
    
    async def _determine_resource_requirements(
        self,
        job_type: JobType,
        model_name: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine resource requirements for a job."""
        # Default requirements based on job type
        requirements = {
            JobType.LLAVA_INFERENCE: {
                "gpu_type": GPUType.RTX4090.value,
                "gpu_count": 4,
                "memory_gb": 96
            },
            JobType.LLAMA_INFERENCE: {
                "gpu_type": GPUType.RTX4090.value,
                "gpu_count": 2,
                "memory_gb": 48
            },
            JobType.TRAINING: {
                "gpu_type": GPUType.A100.value,
                "gpu_count": 1,
                "memory_gb": 80
            },
            JobType.BATCH_PROCESSING: {
                "gpu_type": GPUType.RTX4090.value,
                "gpu_count": 1,
                "memory_gb": 24
            }
        }
        
        return requirements.get(job_type, requirements[JobType.BATCH_PROCESSING])
    
    async def _estimate_job_cost(
        self,
        job_type: JobType,
        resource_requirements: Dict[str, Any],
        runtime_minutes: int
    ) -> float:
        """Estimate cost for a job."""
        gpu_type = GPUType(resource_requirements["gpu_type"])
        gpu_count = resource_requirements["gpu_count"]
        
        # Use first available provider for estimation
        if self.providers:
            provider = next(iter(self.providers.values()))
            return await provider.estimate_cost(gpu_type, gpu_count, runtime_minutes)
        
        # Fallback estimation
        base_cost_per_gpu_hour = 1.0  # $1/hour per GPU
        runtime_hours = runtime_minutes / 60
        return base_cost_per_gpu_hour * gpu_count * runtime_hours