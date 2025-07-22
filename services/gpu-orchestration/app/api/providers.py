#!/usr/bin/env python3
"""
Providers API endpoints for the AIMA GPU Orchestration Service.

This module provides REST API endpoints for GPU provider management.
"""

import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..services.gpu_orchestrator import GPUOrchestrator
from ..models.gpu_models import GPUProvider, GPUType


logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for API
class ProviderStatusResponse(BaseModel):
    """Response model for provider status."""
    provider: str
    status: str
    available_gpu_types: List[str]
    regions: List[str]
    health_check_timestamp: str
    error: Optional[str] = None
    api_latency_ms: Optional[float] = None
    quota_usage: Optional[Dict[str, Any]] = None


class ProviderCapabilitiesResponse(BaseModel):
    """Response model for provider capabilities."""
    provider: str
    supported_gpu_types: List[Dict[str, Any]]
    supported_regions: List[Dict[str, Any]]
    features: List[str]
    pricing_model: str
    min_instance_duration_minutes: int
    max_instance_duration_minutes: int
    supports_preemptible: bool
    supports_spot_instances: bool
    api_rate_limits: Dict[str, int]


class ProviderPricingResponse(BaseModel):
    """Response model for provider pricing."""
    provider: str
    gpu_type: str
    region: str
    hourly_price_usd: float
    spot_price_usd: Optional[float] = None
    preemptible_price_usd: Optional[float] = None
    currency: str = "USD"
    last_updated: str
    price_trend: Optional[str] = None  # "increasing", "decreasing", "stable"


@router.get("/status")
async def get_providers_status(
    orchestrator: GPUOrchestrator = Depends()
):
    """Get status of all configured GPU providers."""
    try:
        logger.info("Getting provider status")
        
        provider_status = await orchestrator.get_provider_status()
        
        # Convert to response format
        status_responses = []
        for provider_name, status_data in provider_status.items():
            response = ProviderStatusResponse(
                provider=provider_name,
                status=status_data.get("status", "unknown"),
                available_gpu_types=status_data.get("available_gpu_types", []),
                regions=status_data.get("regions", []),
                health_check_timestamp=status_data.get("timestamp", ""),
                error=status_data.get("error"),
                api_latency_ms=status_data.get("api_latency_ms"),
                quota_usage=status_data.get("quota_usage")
            )
            status_responses.append(response)
        
        return {"providers": status_responses}
        
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider status")


@router.get("/{provider_name}/status", response_model=ProviderStatusResponse)
async def get_provider_status(
    provider_name: str,
    orchestrator: GPUOrchestrator = Depends()
):
    """Get status of a specific GPU provider."""
    try:
        logger.info("Getting provider status", provider=provider_name)
        
        provider_status = await orchestrator.get_provider_status()
        
        if provider_name not in provider_status:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        
        status_data = provider_status[provider_name]
        
        return ProviderStatusResponse(
            provider=provider_name,
            status=status_data.get("status", "unknown"),
            available_gpu_types=status_data.get("available_gpu_types", []),
            regions=status_data.get("regions", []),
            health_check_timestamp=status_data.get("timestamp", ""),
            error=status_data.get("error"),
            api_latency_ms=status_data.get("api_latency_ms"),
            quota_usage=status_data.get("quota_usage")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for provider {provider_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider status")


@router.get("/capabilities")
async def get_providers_capabilities():
    """Get capabilities of all configured GPU providers."""
    try:
        logger.info("Getting provider capabilities")
        
        # This would query each provider for their capabilities
        # For now, return sample data
        
        capabilities = {
            "runpod": ProviderCapabilitiesResponse(
                provider="runpod",
                supported_gpu_types=[
                    {"type": "RTX4090", "memory_gb": 24, "compute_capability": "8.9"},
                    {"type": "A100", "memory_gb": 80, "compute_capability": "8.0"},
                    {"type": "H100", "memory_gb": 80, "compute_capability": "9.0"}
                ],
                supported_regions=[
                    {"name": "US-East", "code": "us-east", "latency_ms": 50},
                    {"name": "US-West", "code": "us-west", "latency_ms": 80},
                    {"name": "Europe", "code": "eu-central", "latency_ms": 120}
                ],
                features=["auto_scaling", "spot_instances", "custom_images", "ssh_access"],
                pricing_model="hourly",
                min_instance_duration_minutes=1,
                max_instance_duration_minutes=10080,  # 1 week
                supports_preemptible=True,
                supports_spot_instances=True,
                api_rate_limits={"requests_per_minute": 60, "instances_per_hour": 100}
            ),
            "vast": ProviderCapabilitiesResponse(
                provider="vast",
                supported_gpu_types=[
                    {"type": "RTX4090", "memory_gb": 24, "compute_capability": "8.9"},
                    {"type": "A100", "memory_gb": 80, "compute_capability": "8.0"}
                ],
                supported_regions=[
                    {"name": "Global", "code": "global", "latency_ms": 100}
                ],
                features=["spot_instances", "custom_images", "ssh_access"],
                pricing_model="hourly",
                min_instance_duration_minutes=1,
                max_instance_duration_minutes=43200,  # 1 month
                supports_preemptible=False,
                supports_spot_instances=True,
                api_rate_limits={"requests_per_minute": 30, "instances_per_hour": 50}
            )
        }
        
        return {"capabilities": list(capabilities.values())}
        
    except Exception as e:
        logger.error(f"Error getting provider capabilities: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider capabilities")


@router.get("/{provider_name}/capabilities", response_model=ProviderCapabilitiesResponse)
async def get_provider_capabilities(
    provider_name: str
):
    """Get capabilities of a specific GPU provider."""
    try:
        logger.info("Getting provider capabilities", provider=provider_name)
        
        # This would query the specific provider for capabilities
        # For now, return sample data based on provider name
        
        if provider_name == "runpod":
            return ProviderCapabilitiesResponse(
                provider="runpod",
                supported_gpu_types=[
                    {"type": "RTX4090", "memory_gb": 24, "compute_capability": "8.9"},
                    {"type": "A100", "memory_gb": 80, "compute_capability": "8.0"},
                    {"type": "H100", "memory_gb": 80, "compute_capability": "9.0"}
                ],
                supported_regions=[
                    {"name": "US-East", "code": "us-east", "latency_ms": 50},
                    {"name": "US-West", "code": "us-west", "latency_ms": 80},
                    {"name": "Europe", "code": "eu-central", "latency_ms": 120}
                ],
                features=["auto_scaling", "spot_instances", "custom_images", "ssh_access"],
                pricing_model="hourly",
                min_instance_duration_minutes=1,
                max_instance_duration_minutes=10080,
                supports_preemptible=True,
                supports_spot_instances=True,
                api_rate_limits={"requests_per_minute": 60, "instances_per_hour": 100}
            )
        elif provider_name == "vast":
            return ProviderCapabilitiesResponse(
                provider="vast",
                supported_gpu_types=[
                    {"type": "RTX4090", "memory_gb": 24, "compute_capability": "8.9"},
                    {"type": "A100", "memory_gb": 80, "compute_capability": "8.0"}
                ],
                supported_regions=[
                    {"name": "Global", "code": "global", "latency_ms": 100}
                ],
                features=["spot_instances", "custom_images", "ssh_access"],
                pricing_model="hourly",
                min_instance_duration_minutes=1,
                max_instance_duration_minutes=43200,
                supports_preemptible=False,
                supports_spot_instances=True,
                api_rate_limits={"requests_per_minute": 30, "instances_per_hour": 50}
            )
        else:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting capabilities for provider {provider_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider capabilities")


@router.get("/pricing")
async def get_providers_pricing(
    gpu_type: Optional[str] = Query(None, description="Filter by GPU type"),
    region: Optional[str] = Query(None, description="Filter by region")
):
    """Get current pricing from all providers."""
    try:
        logger.info("Getting provider pricing", gpu_type=gpu_type, region=region)
        
        # This would query each provider for current pricing
        # For now, return sample pricing data
        
        pricing_data = [
            ProviderPricingResponse(
                provider="runpod",
                gpu_type="RTX4090",
                region="us-east",
                hourly_price_usd=0.89,
                spot_price_usd=0.45,
                preemptible_price_usd=0.35,
                last_updated="2025-07-22T10:00:00Z",
                price_trend="stable"
            ),
            ProviderPricingResponse(
                provider="runpod",
                gpu_type="A100",
                region="us-east",
                hourly_price_usd=2.89,
                spot_price_usd=1.45,
                preemptible_price_usd=1.15,
                last_updated="2025-07-22T10:00:00Z",
                price_trend="decreasing"
            ),
            ProviderPricingResponse(
                provider="vast",
                gpu_type="RTX4090",
                region="global",
                hourly_price_usd=0.79,
                spot_price_usd=0.39,
                last_updated="2025-07-22T10:00:00Z",
                price_trend="stable"
            ),
            ProviderPricingResponse(
                provider="vast",
                gpu_type="A100",
                region="global",
                hourly_price_usd=2.49,
                spot_price_usd=1.25,
                last_updated="2025-07-22T10:00:00Z",
                price_trend="increasing"
            )
        ]
        
        # Apply filters
        filtered_pricing = pricing_data
        
        if gpu_type:
            filtered_pricing = [p for p in filtered_pricing if p.gpu_type == gpu_type]
        
        if region:
            filtered_pricing = [p for p in filtered_pricing if p.region == region]
        
        return {"pricing": filtered_pricing}
        
    except Exception as e:
        logger.error(f"Error getting provider pricing: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider pricing")


@router.get("/{provider_name}/pricing")
async def get_provider_pricing(
    provider_name: str,
    gpu_type: Optional[str] = Query(None, description="Filter by GPU type"),
    region: Optional[str] = Query(None, description="Filter by region")
):
    """Get current pricing from a specific provider."""
    try:
        logger.info("Getting provider pricing", provider=provider_name, gpu_type=gpu_type, region=region)
        
        # Get all pricing and filter by provider
        all_pricing = await get_providers_pricing(gpu_type, region)
        
        provider_pricing = [
            p for p in all_pricing["pricing"]
            if p.provider == provider_name
        ]
        
        if not provider_pricing:
            raise HTTPException(status_code=404, detail=f"No pricing data found for provider '{provider_name}'")
        
        return {"pricing": provider_pricing}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pricing for provider {provider_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get provider pricing")


@router.get("/comparison")
async def get_pricing_comparison(
    gpu_type: str = Query(..., description="GPU type to compare"),
    region: Optional[str] = Query(None, description="Filter by region")
):
    """Get pricing comparison across all providers for a specific GPU type."""
    try:
        logger.info("Getting pricing comparison", gpu_type=gpu_type, region=region)
        
        # Get pricing for the specific GPU type
        all_pricing = await get_providers_pricing(gpu_type=gpu_type, region=region)
        
        pricing_list = all_pricing["pricing"]
        
        if not pricing_list:
            raise HTTPException(status_code=404, detail=f"No pricing data found for GPU type '{gpu_type}'")
        
        # Sort by hourly price
        pricing_list.sort(key=lambda x: x.hourly_price_usd)
        
        # Calculate comparison metrics
        prices = [p.hourly_price_usd for p in pricing_list]
        cheapest = min(prices)
        most_expensive = max(prices)
        average = sum(prices) / len(prices)
        
        return {
            "gpu_type": gpu_type,
            "region_filter": region,
            "pricing": pricing_list,
            "comparison": {
                "cheapest_price_usd": cheapest,
                "most_expensive_price_usd": most_expensive,
                "average_price_usd": round(average, 2),
                "price_range_usd": round(most_expensive - cheapest, 2),
                "savings_percentage": round((most_expensive - cheapest) / most_expensive * 100, 1) if most_expensive > 0 else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pricing comparison: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pricing comparison")


@router.get("/")
async def list_providers():
    """List all available GPU providers."""
    return {
        "providers": [
            {
                "name": provider.value,
                "description": {
                    GPUProvider.RUNPOD: "RunPod - Serverless GPU cloud platform",
                    GPUProvider.VAST: "Vast.ai - Distributed GPU cloud",
                    GPUProvider.AWS: "Amazon Web Services EC2 GPU instances",
                    GPUProvider.GCP: "Google Cloud Platform GPU instances",
                    GPUProvider.AZURE: "Microsoft Azure GPU instances"
                }.get(provider, "Unknown provider")
            }
            for provider in GPUProvider
        ]
    }