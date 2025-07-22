#!/usr/bin/env python3
"""
Job Manager Service for the AIMA GPU Orchestration Service.

This module implements job queue management, scheduling, and lifecycle operations.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.orm import selectinload

from ..models.gpu_models import (
    GPUInstance, GPUJob, JobTemplate, ResourceQuota,
    JobStatus, JobType, GPUType, GPUProvider
)
from ..core.config import get_settings


logger = logging.getLogger(__name__)


@dataclass
class JobPriority:
    """Job priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 5
    LOW = 8
    BACKGROUND = 10


@dataclass
class QueueMetrics:
    """Queue metrics for monitoring."""
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    average_wait_time_minutes: float
    average_execution_time_minutes: float
    total_cost_usd: float


class JobManager:
    """Manages job queues, scheduling, and lifecycle operations."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Queue management
        self.max_queue_size = 1000
        self.max_concurrent_jobs = self.settings.MAX_CONCURRENT_JOBS
        self.job_timeout_hours = self.settings.JOB_TIMEOUT_HOURS
        
        # Scheduling settings
        self.scheduling_interval_seconds = 30
        self.priority_boost_hours = 24  # Boost priority after waiting
        
        # Job templates cache
        self._job_templates: Dict[str, JobTemplate] = {}
        
        # Active monitoring
        self._scheduler_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the job manager background tasks."""
        if self._running:
            return
        
        self._running = True
        
        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Job Manager started")
    
    async def stop(self):
        """Stop the job manager background tasks."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Job Manager stopped")
    
    async def create_job_template(
        self,
        db: AsyncSession,
        name: str,
        job_type: JobType,
        model_name: str,
        default_config: Dict[str, Any],
        resource_requirements: Dict[str, Any],
        description: Optional[str] = None
    ) -> JobTemplate:
        """Create a new job template."""
        try:
            template = JobTemplate(
                name=name,
                job_type=job_type.value,
                model_name=model_name,
                default_config=default_config,
                resource_requirements=resource_requirements,
                description=description
            )
            
            db.add(template)
            await db.commit()
            await db.refresh(template)
            
            # Update cache
            self._job_templates[name] = template
            
            logger.info("Job template created", template_name=name, job_type=job_type.value)
            
            return template
            
        except Exception as e:
            logger.error("Error creating job template", error=str(e), template_name=name)
            raise
    
    async def get_job_template(self, db: AsyncSession, name: str) -> Optional[JobTemplate]:
        """Get a job template by name."""
        # Check cache first
        if name in self._job_templates:
            return self._job_templates[name]
        
        # Query database
        result = await db.execute(
            select(JobTemplate).where(JobTemplate.name == name)
        )
        template = result.scalar_one_or_none()
        
        if template:
            self._job_templates[name] = template
        
        return template
    
    async def list_job_templates(self, db: AsyncSession) -> List[JobTemplate]:
        """List all available job templates."""
        result = await db.execute(select(JobTemplate).order_by(JobTemplate.name))
        return result.scalars().all()
    
    async def submit_job_from_template(
        self,
        db: AsyncSession,
        user_id: str,
        template_name: str,
        input_data: Dict[str, Any],
        priority: int = JobPriority.NORMAL,
        config_overrides: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> GPUJob:
        """Submit a job using a template."""
        try:
            # Get template
            template = await self.get_job_template(db, template_name)
            if not template:
                raise ValueError(f"Job template '{template_name}' not found")
            
            # Merge configuration
            job_config = template.default_config.copy()
            if config_overrides:
                job_config.update(config_overrides)
            
            # Create job
            job = GPUJob(
                user_id=user_id,
                job_type=template.job_type,
                model_name=template.model_name,
                priority=priority,
                template_name=template_name,
                required_gpu_type=template.resource_requirements.get("gpu_type", GPUType.RTX4090.value),
                required_gpu_count=template.resource_requirements.get("gpu_count", 1),
                required_memory_gb=template.resource_requirements.get("memory_gb", 24),
                max_runtime_minutes=kwargs.get("max_runtime_minutes", job_config.get("max_runtime_minutes", 60)),
                input_data=input_data,
                job_config=job_config,
                status=JobStatus.QUEUED
            )
            
            db.add(job)
            await db.commit()
            await db.refresh(job)
            
            logger.info(
                "Job submitted from template",
                job_id=str(job.id),
                template_name=template_name,
                user_id=user_id,
                priority=priority
            )
            
            return job
            
        except Exception as e:
            logger.error(
                "Error submitting job from template",
                error=str(e),
                template_name=template_name,
                user_id=user_id
            )
            raise
    
    async def get_queue_status(self, db: AsyncSession) -> Dict[str, Any]:
        """Get current queue status and metrics."""
        try:
            # Get job counts by status
            result = await db.execute(
                select(
                    GPUJob.status,
                    func.count(GPUJob.id).label("count")
                )
                .group_by(GPUJob.status)
            )
            
            status_counts = {row.status: row.count for row in result}
            
            # Get queue metrics
            metrics = await self._calculate_queue_metrics(db)
            
            # Get running jobs details
            running_jobs_result = await db.execute(
                select(GPUJob)
                .where(GPUJob.status == JobStatus.RUNNING)
                .options(selectinload(GPUJob.instance))
                .order_by(GPUJob.started_at.desc())
            )
            running_jobs = running_jobs_result.scalars().all()
            
            # Get queued jobs details
            queued_jobs_result = await db.execute(
                select(GPUJob)
                .where(GPUJob.status == JobStatus.QUEUED)
                .order_by(GPUJob.priority.asc(), GPUJob.created_at.asc())
                .limit(20)  # Show next 20 in queue
            )
            queued_jobs = queued_jobs_result.scalars().all()
            
            return {
                "status_counts": status_counts,
                "metrics": {
                    "total_jobs": metrics.total_jobs,
                    "queued_jobs": metrics.queued_jobs,
                    "running_jobs": metrics.running_jobs,
                    "completed_jobs": metrics.completed_jobs,
                    "failed_jobs": metrics.failed_jobs,
                    "average_wait_time_minutes": metrics.average_wait_time_minutes,
                    "average_execution_time_minutes": metrics.average_execution_time_minutes,
                    "total_cost_usd": metrics.total_cost_usd
                },
                "running_jobs": [
                    {
                        "job_id": str(job.id),
                        "user_id": job.user_id,
                        "job_type": job.job_type,
                        "model_name": job.model_name,
                        "priority": job.priority,
                        "progress_percentage": job.progress_percentage,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "estimated_completion_at": job.estimated_completion_at.isoformat() if job.estimated_completion_at else None,
                        "instance_id": str(job.instance.id) if job.instance else None
                    }
                    for job in running_jobs
                ],
                "queued_jobs": [
                    {
                        "job_id": str(job.id),
                        "user_id": job.user_id,
                        "job_type": job.job_type,
                        "model_name": job.model_name,
                        "priority": job.priority,
                        "created_at": job.created_at.isoformat(),
                        "estimated_cost_usd": job.estimated_cost_usd,
                        "queue_position": queued_jobs.index(job) + 1
                    }
                    for job in queued_jobs
                ]
            }
            
        except Exception as e:
            logger.error("Error getting queue status", error=str(e))
            return {}
    
    async def update_job_priority(
        self,
        db: AsyncSession,
        job_id: str,
        user_id: str,
        new_priority: int
    ) -> bool:
        """Update job priority (only for queued jobs)."""
        try:
            result = await db.execute(
                select(GPUJob)
                .where(and_(
                    GPUJob.id == job_id,
                    GPUJob.user_id == user_id,
                    GPUJob.status == JobStatus.QUEUED
                ))
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.warning(
                    "Job not found or not queued",
                    job_id=job_id,
                    user_id=user_id
                )
                return False
            
            old_priority = job.priority
            job.priority = new_priority
            
            await db.commit()
            
            logger.info(
                "Job priority updated",
                job_id=job_id,
                old_priority=old_priority,
                new_priority=new_priority
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Error updating job priority",
                error=str(e),
                job_id=job_id
            )
            return False
    
    async def get_user_quota_status(self, db: AsyncSession, user_id: str) -> Dict[str, Any]:
        """Get user's quota status and usage."""
        try:
            # Get user's resource quota
            result = await db.execute(
                select(ResourceQuota).where(ResourceQuota.user_id == user_id)
            )
            quota = result.scalar_one_or_none()
            
            if not quota:
                # Return default quota
                return {
                    "user_id": user_id,
                    "max_concurrent_jobs": 5,
                    "max_gpu_hours_per_day": 24,
                    "max_cost_per_day_usd": 100.0,
                    "current_concurrent_jobs": 0,
                    "gpu_hours_used_today": 0.0,
                    "cost_used_today_usd": 0.0,
                    "quota_exceeded": False
                }
            
            # Calculate current usage
            today = datetime.utcnow().date()
            
            # Current concurrent jobs
            concurrent_result = await db.execute(
                select(func.count(GPUJob.id))
                .where(and_(
                    GPUJob.user_id == user_id,
                    GPUJob.status.in_([JobStatus.QUEUED, JobStatus.ASSIGNED, JobStatus.RUNNING])
                ))
            )
            current_concurrent = concurrent_result.scalar() or 0
            
            # Today's usage
            usage_result = await db.execute(
                select(
                    func.sum(GPUJob.actual_cost_usd).label("total_cost"),
                    func.sum(
                        func.extract('epoch', GPUJob.completed_at - GPUJob.started_at) / 3600 * GPUJob.required_gpu_count
                    ).label("total_gpu_hours")
                )
                .where(and_(
                    GPUJob.user_id == user_id,
                    func.date(GPUJob.created_at) == today,
                    GPUJob.status == JobStatus.COMPLETED
                ))
            )
            usage = usage_result.first()
            
            cost_used_today = float(usage.total_cost or 0)
            gpu_hours_used_today = float(usage.total_gpu_hours or 0)
            
            # Check if quota exceeded
            quota_exceeded = (
                current_concurrent >= quota.max_concurrent_jobs or
                gpu_hours_used_today >= quota.max_gpu_hours_per_day or
                cost_used_today >= quota.max_cost_per_day_usd
            )
            
            return {
                "user_id": user_id,
                "max_concurrent_jobs": quota.max_concurrent_jobs,
                "max_gpu_hours_per_day": quota.max_gpu_hours_per_day,
                "max_cost_per_day_usd": quota.max_cost_per_day_usd,
                "current_concurrent_jobs": current_concurrent,
                "gpu_hours_used_today": gpu_hours_used_today,
                "cost_used_today_usd": cost_used_today,
                "quota_exceeded": quota_exceeded
            }
            
        except Exception as e:
            logger.error("Error getting user quota status", error=str(e), user_id=user_id)
            return {}
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Job scheduler started")
        
        while self._running:
            try:
                # This would integrate with the GPU orchestrator
                # For now, just log that scheduler is running
                await asyncio.sleep(self.scheduling_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))
                await asyncio.sleep(5)  # Brief pause before retrying
        
        logger.info("Job scheduler stopped")
    
    async def _cleanup_loop(self):
        """Cleanup loop for stale jobs and instances."""
        logger.info("Job cleanup task started")
        
        while self._running:
            try:
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
                
                # This would clean up stale jobs, timeout handling, etc.
                # Implementation would go here
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))
                await asyncio.sleep(60)  # Wait a minute before retrying
        
        logger.info("Job cleanup task stopped")
    
    async def _calculate_queue_metrics(self, db: AsyncSession) -> QueueMetrics:
        """Calculate queue metrics for monitoring."""
        try:
            # Get basic counts
            counts_result = await db.execute(
                select(
                    func.count(GPUJob.id).label("total"),
                    func.sum(func.case([(GPUJob.status == JobStatus.QUEUED, 1)], else_=0)).label("queued"),
                    func.sum(func.case([(GPUJob.status == JobStatus.RUNNING, 1)], else_=0)).label("running"),
                    func.sum(func.case([(GPUJob.status == JobStatus.COMPLETED, 1)], else_=0)).label("completed"),
                    func.sum(func.case([(GPUJob.status == JobStatus.FAILED, 1)], else_=0)).label("failed")
                )
            )
            counts = counts_result.first()
            
            # Calculate average wait time (for completed jobs)
            wait_time_result = await db.execute(
                select(
                    func.avg(
                        func.extract('epoch', GPUJob.started_at - GPUJob.created_at) / 60
                    ).label("avg_wait_minutes")
                )
                .where(and_(
                    GPUJob.status == JobStatus.COMPLETED,
                    GPUJob.started_at.isnot(None)
                ))
            )
            avg_wait_time = wait_time_result.scalar() or 0.0
            
            # Calculate average execution time
            exec_time_result = await db.execute(
                select(
                    func.avg(
                        func.extract('epoch', GPUJob.completed_at - GPUJob.started_at) / 60
                    ).label("avg_exec_minutes")
                )
                .where(and_(
                    GPUJob.status == JobStatus.COMPLETED,
                    GPUJob.started_at.isnot(None),
                    GPUJob.completed_at.isnot(None)
                ))
            )
            avg_exec_time = exec_time_result.scalar() or 0.0
            
            # Calculate total cost
            cost_result = await db.execute(
                select(func.sum(GPUJob.actual_cost_usd).label("total_cost"))
                .where(GPUJob.actual_cost_usd.isnot(None))
            )
            total_cost = cost_result.scalar() or 0.0
            
            return QueueMetrics(
                total_jobs=int(counts.total or 0),
                queued_jobs=int(counts.queued or 0),
                running_jobs=int(counts.running or 0),
                completed_jobs=int(counts.completed or 0),
                failed_jobs=int(counts.failed or 0),
                average_wait_time_minutes=float(avg_wait_time),
                average_execution_time_minutes=float(avg_exec_time),
                total_cost_usd=float(total_cost)
            )
            
        except Exception as e:
            logger.error("Error calculating queue metrics", error=str(e))
            return QueueMetrics(
                total_jobs=0, queued_jobs=0, running_jobs=0,
                completed_jobs=0, failed_jobs=0,
                average_wait_time_minutes=0.0,
                average_execution_time_minutes=0.0,
                total_cost_usd=0.0
            )