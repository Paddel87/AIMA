#!/usr/bin/env python3
"""
Base GPU Provider for the AIMA GPU Orchestration Service.

This module defines the abstract base class for all GPU providers,
establishing the interface and common functionality.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.gpu_models import GPUInstance, GPUJob, InstanceStatus, GPUType


logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class InstanceNotFoundError(ProviderError):
    """Exception raised when instance is not found."""
    pass


class QuotaExceededError(ProviderError):
    """Exception raised when quota is exceeded."""
    pass


class InsufficientResourcesError(ProviderError):
    """Exception raised when insufficient resources are available."""
    pass


class BaseGPUProvider(ABC):
    """Abstract base class for GPU providers."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass
    
    @abstractmethod
    async def create_instance(
        self,
        db: AsyncSession,
        job: GPUJob,
        gpu_type: GPUType,
        gpu_count: int = 1,
        **kwargs
    ) -> GPUInstance:
        """Create a new GPU instance.
        
        Args:
            db: Database session
            job: Job that requires the instance
            gpu_type: Type of GPU required
            gpu_count: Number of GPUs required
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Created GPU instance
            
        Raises:
            ProviderError: If instance creation fails
            QuotaExceededError: If quota is exceeded
            InsufficientResourcesError: If resources are not available
        """
        pass
    
    @abstractmethod
    async def terminate_instance(
        self,
        db: AsyncSession,
        instance: GPUInstance
    ) -> bool:
        """Terminate a GPU instance.
        
        Args:
            db: Database session
            instance: Instance to terminate
            
        Returns:
            True if termination was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_instance_status(
        self,
        instance: GPUInstance
    ) -> InstanceStatus:
        """Get current status of a GPU instance.
        
        Args:
            instance: Instance to check
            
        Returns:
            Current instance status
        """
        pass
    
    @abstractmethod
    async def get_available_gpu_types(self) -> List[Dict[str, Any]]:
        """Get available GPU types and their specifications.
        
        Returns:
            List of available GPU types with specifications
        """
        pass
    
    @abstractmethod
    async def estimate_cost(
        self,
        gpu_type: GPUType,
        gpu_count: int,
        runtime_minutes: int
    ) -> float:
        """Estimate cost for running a job.
        
        Args:
            gpu_type: Type of GPU
            gpu_count: Number of GPUs
            runtime_minutes: Expected runtime in minutes
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the provider.
        
        Returns:
            Health check results
        """
        try:
            # Basic health check - try to get available GPU types
            gpu_types = await self.get_available_gpu_types()
            
            return {
                "provider": self.provider_name,
                "status": "healthy",
                "available_gpu_types": len(gpu_types),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Health check failed for {self.provider_name}", error=str(e))
            return {
                "provider": self.provider_name,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def validate_job_requirements(
        self,
        job: GPUJob,
        gpu_type: GPUType,
        gpu_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Validate if job requirements can be met by this provider.
        
        Args:
            job: Job to validate
            gpu_type: Required GPU type
            gpu_count: Required GPU count
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if GPU type is supported
            available_types = await self.get_available_gpu_types()
            supported_types = [gpu["type"] for gpu in available_types]
            
            if gpu_type.value not in supported_types:
                return False, f"GPU type {gpu_type.value} not supported by {self.provider_name}"
            
            # Check if sufficient GPUs are available
            for gpu_info in available_types:
                if gpu_info["type"] == gpu_type.value:
                    if gpu_info.get("available_count", 0) < gpu_count:
                        return False, f"Insufficient {gpu_type.value} GPUs available (need {gpu_count})"
                    break
            
            # Estimate cost and check against limits
            estimated_cost = await self.estimate_cost(
                gpu_type, gpu_count, job.max_runtime_minutes
            )
            
            if estimated_cost > job.estimated_cost_usd * 1.5:  # 50% buffer
                return False, f"Estimated cost ${estimated_cost:.2f} exceeds job budget"
            
            return True, None
            
        except Exception as e:
            self.logger.error(
                f"Error validating job requirements for {self.provider_name}",
                error=str(e)
            )
            return False, f"Validation error: {str(e)}"
    
    async def get_instance_logs(
        self,
        instance: GPUInstance,
        lines: int = 100
    ) -> List[str]:
        """Get logs from a GPU instance.
        
        Args:
            instance: Instance to get logs from
            lines: Number of log lines to retrieve
            
        Returns:
            List of log lines
        """
        # Default implementation - providers can override
        self.logger.warning(
            f"Log retrieval not implemented for {self.provider_name}"
        )
        return []
    
    async def execute_command(
        self,
        instance: GPUInstance,
        command: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a command on a GPU instance.
        
        Args:
            instance: Instance to execute command on
            command: Command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Command execution result
        """
        # Default implementation - providers can override
        self.logger.warning(
            f"Command execution not implemented for {self.provider_name}"
        )
        return {
            "success": False,
            "error": "Command execution not supported"
        }
    
    async def get_instance_metrics(
        self,
        instance: GPUInstance
    ) -> Dict[str, Any]:
        """Get performance metrics from a GPU instance.
        
        Args:
            instance: Instance to get metrics from
            
        Returns:
            Performance metrics
        """
        # Default implementation - providers can override
        return {
            "provider": self.provider_name,
            "instance_id": str(instance.id),
            "metrics_available": False,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _validate_config(self, required_fields: List[str]) -> None:
        """Validate provider configuration.
        
        Args:
            required_fields: List of required configuration fields
            
        Raises:
            ValueError: If required configuration is missing
        """
        missing_fields = []
        
        for field in required_fields:
            if not hasattr(self, field) or getattr(self, field) is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(
                f"{self.provider_name} provider missing required configuration: {missing_fields}"
            )
    
    def _log_operation(
        self,
        operation: str,
        instance_id: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log provider operation.
        
        Args:
            operation: Operation name
            instance_id: Instance ID if applicable
            job_id: Job ID if applicable
            **kwargs: Additional log data
        """
        log_data = {
            "provider": self.provider_name,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if instance_id:
            log_data["instance_id"] = instance_id
        if job_id:
            log_data["job_id"] = job_id
        
        log_data.update(kwargs)
        
        self.logger.info(f"{self.provider_name} operation: {operation}", **log_data)