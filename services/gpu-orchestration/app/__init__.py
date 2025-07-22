#!/usr/bin/env python3
"""
AIMA GPU Orchestration Service

A comprehensive GPU orchestration service for managing AI workloads
across multiple cloud providers including RunPod, Vast.ai, and AWS.

This service provides:
- Job queue management and scheduling
- Multi-provider GPU instance orchestration
- Cost optimization and resource allocation
- LLaVA and Llama model integration
- Real-time monitoring and metrics
- Auto-scaling and load balancing

Version: 1.0.0
Author: AIMA Team
Date: July 22, 2025
"""

__version__ = "1.0.0"
__author__ = "AIMA Team"
__email__ = "team@aima.ai"
__description__ = "GPU Orchestration Service for AI Workloads"

# Import main components
from .main import app
from .core import get_settings
from .models import *
from .services import GPUOrchestrator, JobManager
from .providers import BaseGPUProvider, RunPodProvider

__all__ = [
    "app",
    "get_settings",
    "GPUOrchestrator",
    "JobManager",
    "BaseGPUProvider",
    "RunPodProvider"
]