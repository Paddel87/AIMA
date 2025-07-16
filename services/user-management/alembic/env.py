#!/usr/bin/env python3
"""
Alembic environment configuration for AIMA User Management Service.

This module configures Alembic for database migrations.
"""

import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import Base
from app.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url():
    """Get database URL from settings."""
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Override the sqlalchemy.url in the alembic config
    config.set_main_option("sqlalchemy.url", get_database_url())
    
    # Set database connection parameters for URL substitution
    # Parse DATABASE_URL for individual components if needed
    import urllib.parse
    parsed = urllib.parse.urlparse(settings.DATABASE_URL)
    config.set_main_option("DB_USER", parsed.username or "")
    config.set_main_option("DB_PASSWORD", parsed.password or "")
    config.set_main_option("DB_HOST", parsed.hostname or "")
    config.set_main_option("DB_PORT", str(parsed.port or 5432))
    config.set_main_option("DB_NAME", parsed.path.lstrip('/') if parsed.path else "")
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            # Include table names in migration
            include_object=include_object,
            # Render item names
            render_item=render_item
        )

        with context.begin_transaction():
            context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """Determine whether to include an object in the migration.
    
    This function can be used to filter out certain tables or columns
    from being included in migrations.
    """
    # Skip tables that are not part of our application
    if type_ == "table":
        # Include only tables that are defined in our models
        return name in target_metadata.tables
    
    return True


def render_item(type_, obj, autogen_context):
    """Apply custom rendering for migration items.
    
    This can be used to customize how certain types are rendered
    in migration files.
    """
    # Use default rendering
    return False


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()