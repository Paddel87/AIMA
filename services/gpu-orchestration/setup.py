#!/usr/bin/env python3
"""
AIMA GPU Orchestration Service Setup

This setup.py file configures the AIMA GPU Orchestration Service as an installable Python package.
It defines dependencies, entry points, and package metadata for proper installation and distribution.
"""

import os
import sys
from pathlib import Path
from setuptools import setup, find_packages

# Ensure we're using Python 3.8+
if sys.version_info < (3, 8):
    raise RuntimeError("AIMA GPU Orchestration Service requires Python 3.8 or higher")

# Get the directory containing this file
HERE = Path(__file__).parent.absolute()

# Read the README file for long description
README_PATH = HERE / "README.md"
if README_PATH.exists():
    with open(README_PATH, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "AIMA GPU Orchestration Service - Intelligent GPU resource management and workload orchestration"

# Read requirements from requirements.txt
REQUIREMENTS_PATH = HERE / "requirements.txt"
if REQUIREMENTS_PATH.exists():
    with open(REQUIREMENTS_PATH, "r", encoding="utf-8") as f:
        requirements = []
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                # Handle version specifiers
                if "==" in line:
                    requirements.append(line)
                elif ">=" in line:
                    requirements.append(line)
                elif "~=" in line:
                    requirements.append(line)
                else:
                    # Add basic package name
                    requirements.append(line)
else:
    # Fallback minimal requirements
    requirements = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "asyncpg>=0.29.0",
        "redis[hiredis]>=5.0.0",
        "httpx>=0.25.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "python-dotenv>=1.0.0",
        "prometheus-client>=0.19.0",
        "structlog>=23.2.0",
        "boto3>=1.34.0",
        "kubernetes>=28.1.0",
    ]

# Development dependencies
dev_requirements = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "black>=23.11.0",
    "isort>=5.12.0",
    "flake8>=6.1.0",
    "mypy>=1.7.0",
    "bandit>=1.7.5",
    "safety>=2.3.5",
    "pre-commit>=3.5.0",
    "jupyter>=1.0.0",
    "ipython>=8.17.0",
    "debugpy>=1.8.0",
]

# Testing dependencies
test_requirements = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.12.0",
    "factory-boy>=3.3.0",
    "faker>=20.1.0",
    "httpx>=0.25.0",
    "locust>=2.17.0",
]

# Documentation dependencies
docs_requirements = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
    "sphinx>=7.2.0",
    "sphinx-rtd-theme>=1.3.0",
]

# Production dependencies (minimal for deployment)
prod_requirements = [
    "gunicorn>=21.2.0",
    "psycopg2-binary>=2.9.9",
    "sentry-sdk>=1.38.0",
]

# GPU-specific dependencies
gpu_requirements = [
    "torch>=2.1.0",
    "transformers>=4.35.0",
    "nvidia-ml-py>=12.535.0",
    "pynvml>=11.5.0",
    "tensorrt>=8.6.0",
    "onnx>=1.15.0",
]

# ML/AI dependencies
ml_requirements = [
    "mlflow>=2.8.0",
    "optuna>=3.4.0",
    "scikit-learn>=1.3.0",
    "pandas>=2.1.0",
    "numpy>=1.25.0",
    "scipy>=1.11.0",
    "matplotlib>=3.8.0",
    "seaborn>=0.13.0",
    "plotly>=5.17.0",
]

# Cloud dependencies
cloud_requirements = [
    "boto3>=1.34.0",
    "kubernetes>=28.1.0",
    "python-terraform>=0.10.0",
    "docker>=6.1.0",
    "ansible>=8.7.0",
]

# Monitoring dependencies
monitoring_requirements = [
    "prometheus-client>=0.19.0",
    "grafana-api>=1.0.0",
    "influxdb-client[async]>=1.38.0",
    "elasticsearch>=8.11.0",
    "loguru>=0.7.0",
]

# Get version from app/__init__.py
version = "1.0.0"
try:
    version_file = HERE / "app" / "__init__.py"
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    version = line.split("=")[1].strip().strip('"').strip("'")
                    break
except Exception:
    pass  # Use default version

# Package configuration
setup(
    # Basic package information
    name="aima-gpu-orchestration",
    version=version,
    description="AIMA GPU Orchestration Service - Intelligent GPU resource management and workload orchestration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    
    # Author and contact information
    author="AIMA Development Team",
    author_email="dev@aima.ai",
    maintainer="AIMA Development Team",
    maintainer_email="dev@aima.ai",
    
    # URLs and links
    url="https://github.com/AIMA/gpu-orchestration",
    project_urls={
        "Homepage": "https://aima.ai",
        "Documentation": "https://docs.aima.ai/gpu-orchestration",
        "Repository": "https://github.com/AIMA/gpu-orchestration",
        "Bug Tracker": "https://github.com/AIMA/gpu-orchestration/issues",
        "Changelog": "https://github.com/AIMA/gpu-orchestration/blob/main/CHANGELOG.md",
    },
    
    # Package discovery and structure
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    package_dir={"": "."},
    include_package_data=True,
    
    # Python version requirements
    python_requires=">=3.8",
    
    # Dependencies
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "test": test_requirements,
        "docs": docs_requirements,
        "prod": prod_requirements,
        "gpu": gpu_requirements,
        "ml": ml_requirements,
        "cloud": cloud_requirements,
        "monitoring": monitoring_requirements,
        "all": (
            dev_requirements +
            test_requirements +
            docs_requirements +
            prod_requirements +
            gpu_requirements +
            ml_requirements +
            cloud_requirements +
            monitoring_requirements
        ),
    },
    
    # Entry points for command-line scripts
    entry_points={
        "console_scripts": [
            "aima-gpu-orchestration=app.cli:main",
            "gpu-orchestration=app.cli:main",
            "aima-gpu=app.cli:main",
        ],
    },
    
    # Package data and resources
    package_data={
        "app": [
            "templates/*.html",
            "templates/*.jinja2",
            "static/*",
            "config/*.yaml",
            "config/*.yml",
            "config/*.json",
            "schemas/*.json",
            "migrations/*.sql",
        ],
    },
    
    # Data files (installed outside the package)
    data_files=[
        ("etc/aima/gpu-orchestration", ["config/default.yaml"]),
        ("var/log/aima", []),
        ("var/lib/aima/gpu-orchestration", []),
    ],
    
    # Classification and metadata
    classifiers=[
        # Development Status
        "Development Status :: 4 - Beta",
        
        # Intended Audience
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        
        # Topic
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Clustering",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        
        # License
        "License :: OSI Approved :: MIT License",
        
        # Operating System
        "Operating System :: OS Independent",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        
        # Programming Language
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        
        # Framework
        "Framework :: FastAPI",
        "Framework :: AsyncIO",
        
        # Environment
        "Environment :: Web Environment",
        "Environment :: Console",
        
        # Natural Language
        "Natural Language :: English",
    ],
    
    # Keywords for package discovery
    keywords=[
        "gpu", "orchestration", "kubernetes", "cloud", "ai", "ml", "machine-learning",
        "deep-learning", "distributed-computing", "resource-management", "scheduling",
        "fastapi", "async", "microservices", "docker", "terraform", "prometheus",
        "grafana", "monitoring", "observability", "cost-optimization", "auto-scaling",
        "multi-cloud", "hybrid-cloud", "edge-computing", "serverless", "containers",
        "devops", "infrastructure", "automation", "cicd", "deployment", "scaling",
        "performance", "optimization", "analytics", "metrics", "logging", "tracing",
        "security", "compliance", "governance", "policy", "rbac", "authentication",
        "authorization", "encryption", "privacy", "gdpr", "hipaa", "sox", "pci",
        "nvidia", "cuda", "tensor", "pytorch", "tensorflow", "transformers", "llm",
        "nlp", "computer-vision", "reinforcement-learning", "federated-learning",
        "model-serving", "inference", "training", "fine-tuning", "hyperparameter",
        "experiment-tracking", "model-registry", "mlops", "aiops", "dataops",
    ],
    
    # License
    license="MIT",
    
    # Zip safety
    zip_safe=False,
    
    # Platform compatibility
    platforms=["any"],
    
    # Additional metadata
    project_urls={
        "Documentation": "https://docs.aima.ai/gpu-orchestration",
        "Funding": "https://github.com/sponsors/AIMA",
        "Source": "https://github.com/AIMA/gpu-orchestration",
        "Tracker": "https://github.com/AIMA/gpu-orchestration/issues",
    },
)

# Post-installation message
if __name__ == "__main__":
    print("\n" + "="*60)
    print("AIMA GPU Orchestration Service Installation Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Copy .env.example to .env and configure your settings")
    print("2. Set up your GPU provider API keys (RunPod, Vast.ai, AWS)")
    print("3. Initialize the database: make db-init")
    print("4. Start the service: make dev")
    print("\nFor more information, see: https://docs.aima.ai/gpu-orchestration")
    print("\nSupport: https://github.com/AIMA/gpu-orchestration/issues")
    print("="*60 + "\n")