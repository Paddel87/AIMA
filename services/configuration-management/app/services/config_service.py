#!/usr/bin/env python3
"""
Configuration service for the AIMA Configuration Management Service.

This module contains the business logic for configuration management operations.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.exc import IntegrityError

from app.models.database import (
    ConfigurationItem,
    ConfigurationHistory,
    ConfigurationTemplate,
    ConfigurationLock
)
from app.models.schemas import (
    ConfigurationItemCreate,
    ConfigurationItemUpdate,
    ConfigurationQuery,
    ConfigDataType,
    ConfigCategory,
    ChangeType
)
from app.core.redis import ConfigurationCache
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfigurationService:
    """Service for configuration management operations."""
    
    def __init__(self, cache: ConfigurationCache):
        self.cache = cache
    
    async def get_configuration(
        self, 
        db: Session, 
        key: str, 
        include_sensitive: bool = False
    ) -> Optional[ConfigurationItem]:
        """Get a single configuration by key."""
        try:
            # Try cache first
            if settings.CONFIG_CACHE_ENABLED:
                cached_value = await self.cache.get(key)
                if cached_value is not None:
                    # Convert cached data back to ConfigurationItem
                    config = ConfigurationItem(**cached_value)
                    if config.is_sensitive and not include_sensitive:
                        config.value = "***MASKED***"
                    return config
            
            # Query database
            config = db.query(ConfigurationItem).filter(
                ConfigurationItem.key == key
            ).first()
            
            if config:
                # Cache the result
                if settings.CONFIG_CACHE_ENABLED and not config.is_sensitive:
                    await self.cache.set(key, {
                        "id": config.id,
                        "key": config.key,
                        "value": config.value,
                        "data_type": config.data_type,
                        "category": config.category,
                        "description": config.description,
                        "is_sensitive": config.is_sensitive,
                        "is_readonly": config.is_readonly,
                        "version": config.version,
                        "created_at": config.created_at.isoformat(),
                        "updated_at": config.updated_at.isoformat()
                    })
                
                # Mask sensitive values if needed
                if config.is_sensitive and not include_sensitive:
                    config.value = "***MASKED***"
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting configuration '{key}': {e}")
            raise
    
    async def get_configurations(
        self, 
        db: Session, 
        query: ConfigurationQuery
    ) -> Tuple[List[ConfigurationItem], int]:
        """Get multiple configurations with filtering and pagination."""
        try:
            # Build query
            db_query = db.query(ConfigurationItem)
            
            # Apply filters
            if query.category:
                db_query = db_query.filter(ConfigurationItem.category == query.category)
            
            if query.key_pattern:
                # Support wildcard patterns
                pattern = query.key_pattern.replace('*', '%')
                db_query = db_query.filter(ConfigurationItem.key.like(pattern))
            
            if not query.include_sensitive:
                db_query = db_query.filter(ConfigurationItem.is_sensitive == False)
            
            if not query.include_readonly:
                db_query = db_query.filter(ConfigurationItem.is_readonly == False)
            
            # Get total count
            total = db_query.count()
            
            # Apply pagination and ordering
            configs = db_query.order_by(
                ConfigurationItem.category,
                ConfigurationItem.key
            ).offset(query.offset).limit(query.limit).all()
            
            # Mask sensitive values
            for config in configs:
                if config.is_sensitive and not query.include_sensitive:
                    config.value = "***MASKED***"
            
            return configs, total
            
        except Exception as e:
            logger.error(f"Error getting configurations: {e}")
            raise
    
    async def create_configuration(
        self, 
        db: Session, 
        config_data: ConfigurationItemCreate
    ) -> ConfigurationItem:
        """Create a new configuration."""
        try:
            # Validate data type
            self._validate_configuration_value(config_data.value, config_data.data_type)
            
            # Check if key already exists
            existing = db.query(ConfigurationItem).filter(
                ConfigurationItem.key == config_data.key
            ).first()
            
            if existing:
                raise ValueError(f"Configuration with key '{config_data.key}' already exists")
            
            # Create configuration
            config = ConfigurationItem(
                key=config_data.key,
                value=config_data.value,
                data_type=config_data.data_type,
                category=config_data.category,
                description=config_data.description,
                is_sensitive=config_data.is_sensitive,
                is_readonly=config_data.is_readonly,
                validation_schema=config_data.validation_schema,
                default_value=config_data.default_value,
                created_by=config_data.created_by,
                version=1
            )
            
            db.add(config)
            db.commit()
            db.refresh(config)
            
            # Create history entry
            await self._create_history_entry(
                db=db,
                config_key=config.key,
                old_value=None,
                new_value=config.value,
                change_type=ChangeType.CREATE,
                changed_by=config_data.created_by,
                version_before=None,
                version_after=config.version
            )
            
            # Cache the new configuration
            if settings.CONFIG_CACHE_ENABLED and not config.is_sensitive:
                await self.cache.set(config.key, {
                    "id": config.id,
                    "key": config.key,
                    "value": config.value,
                    "data_type": config.data_type,
                    "category": config.category,
                    "description": config.description,
                    "is_sensitive": config.is_sensitive,
                    "is_readonly": config.is_readonly,
                    "version": config.version,
                    "created_at": config.created_at.isoformat(),
                    "updated_at": config.updated_at.isoformat()
                })
            
            logger.info(f"Created configuration '{config.key}' by user '{config_data.created_by}'")
            return config
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error creating configuration: {e}")
            raise ValueError(f"Configuration with key '{config_data.key}' already exists")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating configuration: {e}")
            raise
    
    async def update_configuration(
        self, 
        db: Session, 
        key: str, 
        update_data: ConfigurationItemUpdate
    ) -> Optional[ConfigurationItem]:
        """Update an existing configuration."""
        try:
            # Get existing configuration
            config = db.query(ConfigurationItem).filter(
                ConfigurationItem.key == key
            ).first()
            
            if not config:
                return None
            
            # Check if configuration is readonly
            if config.is_readonly:
                raise ValueError(f"Configuration '{key}' is read-only and cannot be updated")
            
            # Check for locks
            lock = db.query(ConfigurationLock).filter(
                ConfigurationLock.config_key == key
            ).first()
            
            if lock and lock.locked_by != update_data.updated_by:
                raise ValueError(f"Configuration '{key}' is locked by user '{lock.locked_by}'")
            
            # Store old values for history
            old_value = config.value
            old_version = config.version
            
            # Update fields
            if update_data.value is not None:
                self._validate_configuration_value(update_data.value, config.data_type)
                config.value = update_data.value
            
            if update_data.description is not None:
                config.description = update_data.description
            
            if update_data.is_sensitive is not None:
                config.is_sensitive = update_data.is_sensitive
            
            if update_data.validation_schema is not None:
                config.validation_schema = update_data.validation_schema
            
            config.updated_by = update_data.updated_by
            config.version += 1
            config.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(config)
            
            # Create history entry
            await self._create_history_entry(
                db=db,
                config_key=config.key,
                old_value=old_value,
                new_value=config.value,
                change_type=ChangeType.UPDATE,
                changed_by=update_data.updated_by,
                change_reason=update_data.change_reason,
                version_before=old_version,
                version_after=config.version
            )
            
            # Update cache
            if settings.CONFIG_CACHE_ENABLED:
                if config.is_sensitive:
                    await self.cache.delete(key)
                else:
                    await self.cache.set(config.key, {
                        "id": config.id,
                        "key": config.key,
                        "value": config.value,
                        "data_type": config.data_type,
                        "category": config.category,
                        "description": config.description,
                        "is_sensitive": config.is_sensitive,
                        "is_readonly": config.is_readonly,
                        "version": config.version,
                        "created_at": config.created_at.isoformat(),
                        "updated_at": config.updated_at.isoformat()
                    })
            
            logger.info(f"Updated configuration '{key}' by user '{update_data.updated_by}'")
            return config
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating configuration '{key}': {e}")
            raise
    
    async def delete_configuration(
        self, 
        db: Session, 
        key: str, 
        deleted_by: Optional[str] = None
    ) -> bool:
        """Delete a configuration."""
        try:
            config = db.query(ConfigurationItem).filter(
                ConfigurationItem.key == key
            ).first()
            
            if not config:
                return False
            
            # Check if configuration is readonly
            if config.is_readonly:
                raise ValueError(f"Configuration '{key}' is read-only and cannot be deleted")
            
            # Store value for history
            old_value = config.value
            old_version = config.version
            
            # Create history entry before deletion
            await self._create_history_entry(
                db=db,
                config_key=config.key,
                old_value=old_value,
                new_value=None,
                change_type=ChangeType.DELETE,
                changed_by=deleted_by,
                version_before=old_version,
                version_after=old_version + 1
            )
            
            # Delete configuration
            db.delete(config)
            db.commit()
            
            # Remove from cache
            if settings.CONFIG_CACHE_ENABLED:
                await self.cache.delete(key)
            
            logger.info(f"Deleted configuration '{key}' by user '{deleted_by}'")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting configuration '{key}': {e}")
            raise
    
    async def get_configuration_history(
        self, 
        db: Session, 
        key: str, 
        limit: int = 50
    ) -> List[ConfigurationHistory]:
        """Get configuration change history."""
        try:
            history = db.query(ConfigurationHistory).filter(
                ConfigurationHistory.config_key == key
            ).order_by(
                ConfigurationHistory.changed_at.desc()
            ).limit(limit).all()
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting configuration history for '{key}': {e}")
            raise
    
    def _validate_configuration_value(self, value: Any, data_type: ConfigDataType) -> None:
        """Validate configuration value against its data type."""
        if not settings.CONFIG_VALIDATION_ENABLED:
            return
        
        try:
            if data_type == ConfigDataType.STRING:
                if not isinstance(value, str):
                    raise ValueError(f"Value must be a string, got {type(value).__name__}")
            
            elif data_type == ConfigDataType.INTEGER:
                if not isinstance(value, int):
                    raise ValueError(f"Value must be an integer, got {type(value).__name__}")
            
            elif data_type == ConfigDataType.FLOAT:
                if not isinstance(value, (int, float)):
                    raise ValueError(f"Value must be a number, got {type(value).__name__}")
            
            elif data_type == ConfigDataType.BOOLEAN:
                if not isinstance(value, bool):
                    raise ValueError(f"Value must be a boolean, got {type(value).__name__}")
            
            elif data_type == ConfigDataType.JSON:
                # Try to serialize to ensure it's valid JSON
                json.dumps(value)
            
            elif data_type == ConfigDataType.ARRAY:
                if not isinstance(value, list):
                    raise ValueError(f"Value must be an array, got {type(value).__name__}")
            
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid value for data type '{data_type}': {e}")
    
    async def _create_history_entry(
        self,
        db: Session,
        config_key: str,
        old_value: Any,
        new_value: Any,
        change_type: ChangeType,
        changed_by: Optional[str],
        change_reason: Optional[str] = None,
        version_before: Optional[int] = None,
        version_after: int = 1
    ) -> None:
        """Create a configuration history entry."""
        if not settings.CONFIG_AUDIT_ENABLED:
            return
        
        try:
            history = ConfigurationHistory(
                config_key=config_key,
                old_value=old_value,
                new_value=new_value,
                change_type=change_type,
                changed_by=changed_by,
                change_reason=change_reason,
                version_before=version_before,
                version_after=version_after
            )
            
            db.add(history)
            # Note: Don't commit here, let the caller handle the transaction
            
        except Exception as e:
            logger.error(f"Error creating history entry for '{config_key}': {e}")
            # Don't raise here to avoid breaking the main operation
    
    async def get_metrics(self, db: Session) -> Dict[str, Any]:
        """Get configuration metrics."""
        try:
            # Total configurations
            total_configs = db.query(ConfigurationItem).count()
            
            # Configurations by category
            category_counts = db.query(
                ConfigurationItem.category,
                func.count(ConfigurationItem.id)
            ).group_by(ConfigurationItem.category).all()
            
            configs_by_category = {category: count for category, count in category_counts}
            
            # Recent changes (last 24 hours)
            from datetime import timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_changes = db.query(ConfigurationHistory).filter(
                ConfigurationHistory.changed_at >= yesterday
            ).count()
            
            # Cache stats
            cache_stats = await self.cache.get_cache_stats()
            cache_hit_rate = 0.0  # This would need to be tracked separately
            
            return {
                "total_configurations": total_configs,
                "configurations_by_category": configs_by_category,
                "recent_changes": recent_changes,
                "cache_hit_rate": cache_hit_rate,
                "cache_stats": cache_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting configuration metrics: {e}")
            raise