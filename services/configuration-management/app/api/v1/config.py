#!/usr/bin/env python3
"""
Configuration API endpoints for the AIMA Configuration Management Service.

This module implements the REST API endpoints for configuration management
as defined in the API_MAPPING.md document.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis import get_cache, ConfigurationCache
from app.services.config_service import ConfigurationService
from app.models.schemas import (
    ConfigurationItemCreate,
    ConfigurationItemUpdate,
    ConfigurationItemResponse,
    ConfigurationItemFullResponse,
    ConfigurationListResponse,
    ConfigurationQuery,
    ConfigurationHistoryResponse,
    BulkConfigurationUpdate,
    BulkConfigurationResponse,
    MetricsResponse,
    ErrorResponse,
    ConfigCategory
)
from app.api.dependencies import (
    get_current_user,
    require_admin,
    get_config_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["Configuration Management"])


@router.get(
    "/",
    response_model=ConfigurationListResponse,
    summary="Get all configurations",
    description="Retrieve all system configurations with optional filtering and pagination."
)
async def get_configurations(
    category: Optional[ConfigCategory] = Query(None, description="Filter by category"),
    key_pattern: Optional[str] = Query(None, description="Filter by key pattern (supports wildcards)"),
    include_sensitive: bool = Query(False, description="Include sensitive configurations (admin only)"),
    include_readonly: bool = Query(True, description="Include read-only configurations"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConfigurationListResponse:
    """Get all configurations with filtering and pagination."""
    try:
        # Only admins can view sensitive configurations
        if include_sensitive and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can view sensitive configurations"
            )
        
        query = ConfigurationQuery(
            category=category,
            key_pattern=key_pattern,
            include_sensitive=include_sensitive,
            include_readonly=include_readonly,
            limit=limit,
            offset=offset
        )
        
        configs, total = await config_service.get_configurations(db, query)
        
        return ConfigurationListResponse(
            items=[ConfigurationItemResponse.from_orm(config) for config in configs],
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Error getting configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configurations"
        )


@router.get(
    "/{key}",
    response_model=ConfigurationItemResponse,
    summary="Get configuration by key",
    description="Retrieve a specific configuration by its key."
)
async def get_configuration(
    key: str,
    include_sensitive: bool = Query(False, description="Include sensitive value (admin only)"),
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ConfigurationItemResponse:
    """Get a specific configuration by key."""
    try:
        # Only admins can view sensitive configurations
        if include_sensitive and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can view sensitive configurations"
            )
        
        config = await config_service.get_configuration(
            db, key, include_sensitive=include_sensitive
        )
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration with key '{key}' not found"
            )
        
        if include_sensitive and current_user.get("role") == "admin":
            return ConfigurationItemFullResponse.from_orm(config)
        else:
            return ConfigurationItemResponse.from_orm(config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting configuration '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration"
        )


@router.post(
    "/",
    response_model=ConfigurationItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create configuration",
    description="Create a new system configuration."
)
async def create_configuration(
    config_data: ConfigurationItemCreate,
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> ConfigurationItemResponse:
    """Create a new configuration (admin only)."""
    try:
        # Set the creator
        config_data.created_by = current_user.get("user_id")
        
        config = await config_service.create_configuration(db, config_data)
        
        return ConfigurationItemResponse.from_orm(config)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create configuration"
        )


@router.put(
    "/{key}",
    response_model=ConfigurationItemResponse,
    summary="Update configuration",
    description="Update an existing configuration by key."
)
async def update_configuration(
    key: str,
    update_data: ConfigurationItemUpdate,
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> ConfigurationItemResponse:
    """Update an existing configuration (admin only)."""
    try:
        # Set the updater
        update_data.updated_by = current_user.get("user_id")
        
        config = await config_service.update_configuration(db, key, update_data)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration with key '{key}' not found"
            )
        
        return ConfigurationItemResponse.from_orm(config)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update configuration"
        )


@router.delete(
    "/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete configuration",
    description="Delete a configuration by key."
)
async def delete_configuration(
    key: str,
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> None:
    """Delete a configuration (admin only)."""
    try:
        deleted = await config_service.delete_configuration(
            db, key, deleted_by=current_user.get("user_id")
        )
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration with key '{key}' not found"
            )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting configuration '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete configuration"
        )


@router.get(
    "/{key}/history",
    response_model=List[ConfigurationHistoryResponse],
    summary="Get configuration history",
    description="Get the change history for a specific configuration."
)
async def get_configuration_history(
    key: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of history entries"),
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> List[ConfigurationHistoryResponse]:
    """Get configuration change history (admin only)."""
    try:
        history = await config_service.get_configuration_history(db, key, limit)
        
        return [ConfigurationHistoryResponse.from_orm(entry) for entry in history]
        
    except Exception as e:
        logger.error(f"Error getting configuration history for '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration history"
        )


@router.post(
    "/bulk",
    response_model=BulkConfigurationResponse,
    summary="Bulk update configurations",
    description="Update multiple configurations in a single operation."
)
async def bulk_update_configurations(
    bulk_update: BulkConfigurationUpdate,
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> BulkConfigurationResponse:
    """Bulk update configurations (admin only)."""
    try:
        success_count = 0
        error_count = 0
        errors = []
        
        for config_update in bulk_update.configurations:
            try:
                key = config_update.get("key")
                if not key:
                    errors.append({"key": "unknown", "error": "Missing key"})
                    error_count += 1
                    continue
                
                update_data = ConfigurationItemUpdate(
                    value=config_update.get("value"),
                    description=config_update.get("description"),
                    is_sensitive=config_update.get("is_sensitive"),
                    updated_by=bulk_update.updated_by or current_user.get("user_id"),
                    change_reason=bulk_update.change_reason
                )
                
                result = await config_service.update_configuration(db, key, update_data)
                if result:
                    success_count += 1
                else:
                    errors.append({"key": key, "error": "Configuration not found"})
                    error_count += 1
                    
            except Exception as e:
                errors.append({"key": config_update.get("key", "unknown"), "error": str(e)})
                error_count += 1
        
        return BulkConfigurationResponse(
            success_count=success_count,
            error_count=error_count,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Error in bulk configuration update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk update"
        )


@router.get(
    "/system/metrics",
    response_model=MetricsResponse,
    summary="Get configuration metrics",
    description="Get system metrics for configuration management."
)
async def get_configuration_metrics(
    db: Session = Depends(get_db),
    config_service: ConfigurationService = Depends(get_config_service),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> MetricsResponse:
    """Get configuration metrics (admin only)."""
    try:
        metrics = await config_service.get_metrics(db)
        
        return MetricsResponse(**metrics)
        
    except Exception as e:
        logger.error(f"Error getting configuration metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.post(
    "/cache/clear",
    summary="Clear configuration cache",
    description="Clear all cached configuration data."
)
async def clear_configuration_cache(
    cache: ConfigurationCache = Depends(get_cache),
    current_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, str]:
    """Clear configuration cache (admin only)."""
    try:
        success = await cache.clear_all()
        
        if success:
            return {"message": "Configuration cache cleared successfully"}
        else:
            return {"message": "Cache clearing failed or cache is disabled"}
        
    except Exception as e:
        logger.error(f"Error clearing configuration cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )