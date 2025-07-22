#!/usr/bin/env python3
"""
RunPod GPU Provider for the AIMA GPU Orchestration Service.

This module implements the RunPod API integration for managing GPU instances,
including instance creation, monitoring, and termination.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.gpu_models import GPUInstance, GPUJob, InstanceStatus, JobStatus, GPUType
from ..core.config import get_settings
from .base_provider import BaseGPUProvider, ProviderError, InstanceNotFoundError


logger = logging.getLogger(__name__)


class RunPodProvider(BaseGPUProvider):
    """RunPod GPU provider implementation."""
    
    def __init__(self):
        super().__init__()
        self.settings = get_settings()
        self.api_key = self.settings.RUNPOD_API_KEY
        self.api_url = self.settings.RUNPOD_API_URL
        self.webhook_secret = self.settings.RUNPOD_WEBHOOK_SECRET
        
        if not self.api_key:
            raise ValueError("RunPod API key not configured")
        
        # GPU type mapping
        self.gpu_type_mapping = {
            GPUType.RTX4090: "NVIDIA GeForce RTX 4090",
            GPUType.RTX3090: "NVIDIA GeForce RTX 3090",
            GPUType.A100: "NVIDIA A100-SXM4-80GB",
            GPUType.H100: "NVIDIA H100-SXM5-80GB",
            GPUType.V100: "Tesla V100-SXM2-32GB",
            GPUType.T4: "Tesla T4"
        }
        
        # Docker images for different job types
        self.docker_images = {
            "llava_inference": "runpod/llava:1.6-34b",
            "llama_inference": "runpod/llama:3.1-70b",
            "training": "runpod/pytorch:2.0-cuda11.8",
            "custom": "runpod/pytorch:2.0-cuda11.8"
        }
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "runpod"
    
    async def create_instance(
        self,
        db: AsyncSession,
        job: GPUJob,
        gpu_type: GPUType,
        gpu_count: int = 1,
        **kwargs
    ) -> GPUInstance:
        """Create a new GPU instance on RunPod."""
        try:
            logger.info(
                "Creating RunPod instance",
                job_id=str(job.id),
                gpu_type=gpu_type.value,
                gpu_count=gpu_count
            )
            
            # Prepare instance configuration
            config = await self._prepare_instance_config(
                job, gpu_type, gpu_count, **kwargs
            )
            
            # Create instance via GraphQL API
            response = await self._create_pod(config)
            
            if not response.get("success"):
                raise ProviderError(f"Failed to create RunPod instance: {response.get('error')}")
            
            pod_data = response["data"]
            
            # Create database record
            instance = GPUInstance(
                provider="runpod",
                provider_instance_id=pod_data["id"],
                gpu_type=gpu_type.value,
                gpu_count=gpu_count,
                memory_gb=self._get_memory_for_gpu_type(gpu_type) * gpu_count,
                vcpus=self._get_vcpus_for_gpu_type(gpu_type) * gpu_count,
                storage_gb=config.get("volumeInGb", 50),
                status=InstanceStatus.PENDING,
                hourly_cost_usd=self._calculate_hourly_cost(gpu_type, gpu_count),
                docker_image=config["imageName"],
                environment_vars=config.get("env", {}),
                region=config.get("dataCenterId"),
                preemptible=config.get("bidPerGpu") is not None,
                provider_metadata={
                    "pod_id": pod_data["id"],
                    "machine_id": pod_data.get("machineId"),
                    "data_center_id": config.get("dataCenterId"),
                    "bid_per_gpu": config.get("bidPerGpu")
                }
            )
            
            db.add(instance)
            await db.commit()
            await db.refresh(instance)
            
            # Start monitoring the instance
            asyncio.create_task(self._monitor_instance(db, instance))
            
            logger.info(
                "RunPod instance created successfully",
                instance_id=str(instance.id),
                pod_id=pod_data["id"]
            )
            
            return instance
            
        except Exception as e:
            logger.error("Failed to create RunPod instance", error=str(e), job_id=str(job.id))
            raise ProviderError(f"Failed to create RunPod instance: {str(e)}")
    
    async def terminate_instance(self, db: AsyncSession, instance: GPUInstance) -> bool:
        """Terminate a GPU instance on RunPod."""
        try:
            logger.info(
                "Terminating RunPod instance",
                instance_id=str(instance.id),
                pod_id=instance.provider_instance_id
            )
            
            # Terminate pod via API
            response = await self._terminate_pod(instance.provider_instance_id)
            
            if response.get("success"):
                # Update instance status
                instance.status = InstanceStatus.TERMINATED
                instance.stopped_at = datetime.utcnow()
                
                # Calculate final cost
                if instance.started_at:
                    runtime_hours = (
                        instance.stopped_at - instance.started_at
                    ).total_seconds() / 3600
                    instance.total_cost_usd = runtime_hours * instance.hourly_cost_usd
                
                await db.commit()
                
                logger.info(
                    "RunPod instance terminated successfully",
                    instance_id=str(instance.id),
                    total_cost=instance.total_cost_usd
                )
                return True
            else:
                logger.error(
                    "Failed to terminate RunPod instance",
                    instance_id=str(instance.id),
                    error=response.get("error")
                )
                return False
                
        except Exception as e:
            logger.error(
                "Error terminating RunPod instance",
                instance_id=str(instance.id),
                error=str(e)
            )
            return False
    
    async def get_instance_status(self, instance: GPUInstance) -> InstanceStatus:
        """Get current status of a GPU instance."""
        try:
            response = await self._get_pod_status(instance.provider_instance_id)
            
            if not response.get("success"):
                logger.warning(
                    "Failed to get RunPod instance status",
                    instance_id=str(instance.id),
                    error=response.get("error")
                )
                return InstanceStatus.FAILED
            
            pod_data = response["data"]
            runpod_status = pod_data.get("desiredStatus", "UNKNOWN")
            
            # Map RunPod status to our status
            status_mapping = {
                "RUNNING": InstanceStatus.RUNNING,
                "STOPPED": InstanceStatus.STOPPED,
                "EXITED": InstanceStatus.TERMINATED,
                "FAILED": InstanceStatus.FAILED,
                "PENDING": InstanceStatus.PENDING,
                "STARTING": InstanceStatus.STARTING
            }
            
            return status_mapping.get(runpod_status, InstanceStatus.FAILED)
            
        except Exception as e:
            logger.error(
                "Error getting RunPod instance status",
                instance_id=str(instance.id),
                error=str(e)
            )
            return InstanceStatus.FAILED
    
    async def get_available_gpu_types(self) -> List[Dict[str, Any]]:
        """Get available GPU types and their pricing."""
        try:
            response = await self._get_gpu_types()
            
            if not response.get("success"):
                logger.error("Failed to get RunPod GPU types", error=response.get("error"))
                return []
            
            gpu_types = []
            for gpu_data in response["data"]:
                gpu_types.append({
                    "type": gpu_data["displayName"],
                    "memory_gb": gpu_data["memoryInGb"],
                    "hourly_cost_usd": gpu_data["lowestPrice"]["minimumBidPrice"],
                    "available_count": gpu_data["lowestPrice"]["uninterruptablePrice"],
                    "regions": [dc["id"] for dc in gpu_data["dataCenters"]]
                })
            
            return gpu_types
            
        except Exception as e:
            logger.error("Error getting RunPod GPU types", error=str(e))
            return []
    
    async def estimate_cost(
        self,
        gpu_type: GPUType,
        gpu_count: int,
        runtime_minutes: int
    ) -> float:
        """Estimate cost for running a job."""
        hourly_cost = self._calculate_hourly_cost(gpu_type, gpu_count)
        runtime_hours = runtime_minutes / 60
        return hourly_cost * runtime_hours
    
    async def _prepare_instance_config(
        self,
        job: GPUJob,
        gpu_type: GPUType,
        gpu_count: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Prepare instance configuration for RunPod API."""
        # Get appropriate Docker image
        docker_image = self.docker_images.get(
            job.job_type,
            self.docker_images["custom"]
        )
        
        # Prepare environment variables
        env_vars = {
            "JOB_ID": str(job.id),
            "JOB_TYPE": job.job_type,
            "MODEL_NAME": job.model_name,
            "GPU_COUNT": str(gpu_count),
            "AIMA_API_ENDPOINT": kwargs.get("api_endpoint", "http://localhost:8000")
        }
        
        # Add job-specific environment variables
        if job.input_data:
            env_vars.update(job.input_data.get("environment", {}))
        
        config = {
            "name": f"aima-{job.job_type}-{str(job.id)[:8]}",
            "imageName": docker_image,
            "gpuTypeId": self.gpu_type_mapping.get(gpu_type, gpu_type.value),
            "gpuCount": gpu_count,
            "volumeInGb": kwargs.get("storage_gb", 50),
            "containerDiskInGb": kwargs.get("container_disk_gb", 20),
            "env": env_vars,
            "ports": "8000/http,22/tcp",
            "volumeMountPath": "/workspace"
        }
        
        # Add data center preference
        if kwargs.get("region"):
            config["dataCenterId"] = kwargs["region"]
        
        # Add bid price for spot instances
        if kwargs.get("use_spot", True):
            config["bidPerGpu"] = self._calculate_bid_price(gpu_type)
        
        return config
    
    async def _create_pod(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create pod via RunPod GraphQL API."""
        mutation = """
        mutation createPod($input: PodRentInterruptableInput!) {
            podRentInterruptable(input: $input) {
                id
                machineId
                machine {
                    podHostId
                }
            }
        }
        """
        
        variables = {"input": config}
        
        return await self._graphql_request(mutation, variables)
    
    async def _terminate_pod(self, pod_id: str) -> Dict[str, Any]:
        """Terminate pod via RunPod API."""
        mutation = """
        mutation terminatePod($input: PodTerminateInput!) {
            podTerminate(input: $input) {
                id
            }
        }
        """
        
        variables = {"input": {"podId": pod_id}}
        
        return await self._graphql_request(mutation, variables)
    
    async def _get_pod_status(self, pod_id: str) -> Dict[str, Any]:
        """Get pod status via RunPod API."""
        query = """
        query getPod($podId: String!) {
            pod(id: $podId) {
                id
                desiredStatus
                lastStatusChange
                machine {
                    podHostId
                }
                runtime {
                    uptimeInSeconds
                    ports {
                        ip
                        isIpPublic
                        privatePort
                        publicPort
                        type
                    }
                }
            }
        }
        """
        
        variables = {"podId": pod_id}
        
        return await self._graphql_request(query, variables)
    
    async def _get_gpu_types(self) -> Dict[str, Any]:
        """Get available GPU types via RunPod API."""
        query = """
        query getGpuTypes {
            gpuTypes {
                id
                displayName
                memoryInGb
                lowestPrice {
                    minimumBidPrice
                    uninterruptablePrice
                }
                dataCenters {
                    id
                    name
                }
            }
        }
        """
        
        return await self._graphql_request(query, {})
    
    async def _graphql_request(
        self,
        query: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make GraphQL request to RunPod API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "variables": variables
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise ProviderError(
                    f"RunPod API request failed: {response.status_code} {response.text}"
                )
            
            data = response.json()
            
            if "errors" in data:
                raise ProviderError(f"RunPod GraphQL errors: {data['errors']}")
            
            return {
                "success": True,
                "data": data.get("data", {})
            }
    
    def _calculate_hourly_cost(self, gpu_type: GPUType, gpu_count: int) -> float:
        """Calculate hourly cost for GPU configuration."""
        # Base costs per GPU per hour (approximate)
        base_costs = {
            GPUType.RTX4090: 0.50,
            GPUType.RTX3090: 0.40,
            GPUType.A100: 2.50,
            GPUType.H100: 4.00,
            GPUType.V100: 1.50,
            GPUType.T4: 0.30
        }
        
        return base_costs.get(gpu_type, 1.0) * gpu_count
    
    def _calculate_bid_price(self, gpu_type: GPUType) -> float:
        """Calculate bid price for spot instances."""
        hourly_cost = self._calculate_hourly_cost(gpu_type, 1)
        # Bid 80% of on-demand price
        return hourly_cost * 0.8
    
    def _get_memory_for_gpu_type(self, gpu_type: GPUType) -> int:
        """Get memory in GB for GPU type."""
        memory_mapping = {
            GPUType.RTX4090: 24,
            GPUType.RTX3090: 24,
            GPUType.A100: 80,
            GPUType.H100: 80,
            GPUType.V100: 32,
            GPUType.T4: 16
        }
        return memory_mapping.get(gpu_type, 24)
    
    def _get_vcpus_for_gpu_type(self, gpu_type: GPUType) -> int:
        """Get vCPUs for GPU type."""
        vcpu_mapping = {
            GPUType.RTX4090: 8,
            GPUType.RTX3090: 8,
            GPUType.A100: 16,
            GPUType.H100: 16,
            GPUType.V100: 12,
            GPUType.T4: 4
        }
        return vcpu_mapping.get(gpu_type, 8)
    
    async def _monitor_instance(self, db: AsyncSession, instance: GPUInstance):
        """Monitor instance status and update database."""
        try:
            while instance.status in [InstanceStatus.PENDING, InstanceStatus.STARTING, InstanceStatus.RUNNING]:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_status = await self.get_instance_status(instance)
                
                if current_status != instance.status:
                    logger.info(
                        "RunPod instance status changed",
                        instance_id=str(instance.id),
                        old_status=instance.status,
                        new_status=current_status
                    )
                    
                    instance.status = current_status
                    instance.last_heartbeat = datetime.utcnow()
                    
                    if current_status == InstanceStatus.RUNNING and not instance.started_at:
                        instance.started_at = datetime.utcnow()
                    elif current_status in [InstanceStatus.STOPPED, InstanceStatus.TERMINATED]:
                        instance.stopped_at = datetime.utcnow()
                        break
                    
                    await db.commit()
                
        except Exception as e:
            logger.error(
                "Error monitoring RunPod instance",
                instance_id=str(instance.id),
                error=str(e)
            )