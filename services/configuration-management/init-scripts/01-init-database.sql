-- Database initialization script for AIMA Configuration Management Service
-- This script sets up the initial database schema and default data

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types
DO $$ BEGIN
    CREATE TYPE config_data_type AS ENUM (
        'string', 'integer', 'float', 'boolean', 'json', 'array'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE config_category AS ENUM (
        'system', 'database', 'security', 'performance', 'integration', 'ui', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE config_change_type AS ENUM (
        'created', 'updated', 'deleted', 'restored'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for better performance
-- Note: Tables will be created by SQLAlchemy, but we can add additional indexes here

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Function to validate JSON data
CREATE OR REPLACE FUNCTION validate_json_value(value_text TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    BEGIN
        PERFORM value_text::json;
        RETURN TRUE;
    EXCEPTION WHEN invalid_text_representation THEN
        RETURN FALSE;
    END;
END;
$$ LANGUAGE plpgsql;

-- Function to validate configuration value based on data type
CREATE OR REPLACE FUNCTION validate_config_value(
    value_text TEXT,
    data_type config_data_type
)
RETURNS BOOLEAN AS $$
BEGIN
    CASE data_type
        WHEN 'string' THEN
            RETURN TRUE; -- Any text is valid for string
        WHEN 'integer' THEN
            BEGIN
                PERFORM value_text::INTEGER;
                RETURN TRUE;
            EXCEPTION WHEN invalid_text_representation THEN
                RETURN FALSE;
            END;
        WHEN 'float' THEN
            BEGIN
                PERFORM value_text::FLOAT;
                RETURN TRUE;
            EXCEPTION WHEN invalid_text_representation THEN
                RETURN FALSE;
            END;
        WHEN 'boolean' THEN
            RETURN value_text::TEXT IN ('true', 'false', 't', 'f', '1', '0', 'yes', 'no', 'on', 'off');
        WHEN 'json' THEN
            RETURN validate_json_value(value_text);
        WHEN 'array' THEN
            BEGIN
                PERFORM value_text::json;
                -- Check if it's actually an array
                RETURN json_typeof(value_text::json) = 'array';
            EXCEPTION WHEN invalid_text_representation THEN
                RETURN FALSE;
            END;
        ELSE
            RETURN FALSE;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Views will be created in post-init script after tables are created by SQLAlchemy

-- Grant permissions
GRANT USAGE ON SCHEMA public TO config_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO config_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO config_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO config_user;

-- Log completion
\echo 'Database pre-initialization completed successfully'