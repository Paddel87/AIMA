#!/usr/bin/env python3
"""
Database models for the AIMA Configuration Management Service.

This module defines the SQLAlchemy models for configuration storage.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    JSON,
    Index,
    UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ConfigurationItem(Base):
    """Configuration item model."""
    
    __tablename__ = "configuration_items"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, index=True, nullable=False)
    value = Column(JSON, nullable=False)
    data_type = Column(String(50), nullable=False)  # string, integer, boolean, json, array
    category = Column(String(100), nullable=False, index=True)  # system, feature_flags, models, gpu_providers
    description = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    is_readonly = Column(Boolean, default=False, nullable=False)
    validation_schema = Column(JSON, nullable=True)  # JSON schema for validation
    default_value = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)  # User ID who created this config
    updated_by = Column(String(255), nullable=True)  # User ID who last updated this config
    
    # Versioning
    version = Column(Integer, default=1, nullable=False)
    
    __table_args__ = (
        Index('idx_config_category_key', 'category', 'key'),
        Index('idx_config_updated_at', 'updated_at'),
    )
    
    def __repr__(self):
        return f"<ConfigurationItem(key='{self.key}', category='{self.category}', version={self.version})>"


class ConfigurationHistory(Base):
    """Configuration change history model."""
    
    __tablename__ = "configuration_history"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(255), nullable=False, index=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=False)
    change_type = Column(String(20), nullable=False)  # create, update, delete
    changed_by = Column(String(255), nullable=True)  # User ID who made the change
    change_reason = Column(Text, nullable=True)
    
    # Metadata
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    version_before = Column(Integer, nullable=True)
    version_after = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index('idx_config_history_key_time', 'config_key', 'changed_at'),
        Index('idx_config_history_changed_by', 'changed_by'),
    )
    
    def __repr__(self):
        return f"<ConfigurationHistory(key='{self.config_key}', type='{self.change_type}', version={self.version_after})>"


class ConfigurationTemplate(Base):
    """Configuration template model for predefined configurations."""
    
    __tablename__ = "configuration_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    template_data = Column(JSON, nullable=False)  # Template configuration data
    category = Column(String(100), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(255), nullable=True)
    
    def __repr__(self):
        return f"<ConfigurationTemplate(name='{self.name}', category='{self.category}')>"


class ConfigurationLock(Base):
    """Configuration lock model to prevent concurrent modifications."""
    
    __tablename__ = "configuration_locks"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(255), unique=True, index=True, nullable=False)
    locked_by = Column(String(255), nullable=False)  # User ID who locked the config
    lock_reason = Column(String(255), nullable=True)
    
    # Metadata
    locked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Auto-unlock time
    
    def __repr__(self):
        return f"<ConfigurationLock(key='{self.config_key}', locked_by='{self.locked_by}')>"