-- AIMA GPU Orchestration Service Database Initialization
-- This script initializes the PostgreSQL database for the GPU orchestration service

-- Create database if it doesn't exist (handled by Docker)
-- CREATE DATABASE gpu_orchestration;

-- Connect to the database
\c gpu_orchestration;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types for enums
DO $$ BEGIN
    -- GPU Provider enum
    CREATE TYPE gpu_provider AS ENUM (
        'runpod',
        'vast',
        'aws',
        'gcp',
        'azure'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- GPU Type enum
    CREATE TYPE gpu_type AS ENUM (
        'RTX4090',
        'RTX3090',
        'RTX3080',
        'A100',
        'A6000',
        'V100',
        'T4',
        'H100'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Instance Status enum
    CREATE TYPE instance_status AS ENUM (
        'pending',
        'starting',
        'running',
        'stopping',
        'stopped',
        'terminated',
        'error'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Job Status enum
    CREATE TYPE job_status AS ENUM (
        'queued',
        'pending',
        'running',
        'completed',
        'failed',
        'cancelled',
        'timeout'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Job Type enum
    CREATE TYPE job_type AS ENUM (
        'llava',
        'llama',
        'training',
        'batch_processing',
        'inference',
        'custom'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    -- Job Priority enum
    CREATE TYPE job_priority AS ENUM (
        'low',
        'normal',
        'high',
        'urgent'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for better performance
-- These will be created automatically by SQLAlchemy, but we can add custom ones here

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create a function to generate job IDs
CREATE OR REPLACE FUNCTION generate_job_id()
RETURNS TEXT AS $$
BEGIN
    RETURN 'job-' || EXTRACT(EPOCH FROM NOW())::BIGINT || '-' || SUBSTRING(MD5(RANDOM()::TEXT) FROM 1 FOR 8);
END;
$$ LANGUAGE plpgsql;

-- Create a function to generate instance IDs
CREATE OR REPLACE FUNCTION generate_instance_id()
RETURNS TEXT AS $$
BEGIN
    RETURN 'inst-' || EXTRACT(EPOCH FROM NOW())::BIGINT || '-' || SUBSTRING(MD5(RANDOM()::TEXT) FROM 1 FOR 8);
END;
$$ LANGUAGE plpgsql;

-- Create a function to calculate job cost
CREATE OR REPLACE FUNCTION calculate_job_cost(
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    hourly_rate DECIMAL
)
RETURNS DECIMAL AS $$
DECLARE
    duration_hours DECIMAL;
BEGIN
    IF start_time IS NULL OR end_time IS NULL OR hourly_rate IS NULL THEN
        RETURN 0;
    END IF;
    
    duration_hours := EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0;
    RETURN ROUND(duration_hours * hourly_rate, 4);
END;
$$ LANGUAGE plpgsql;

-- Create a view for job statistics
CREATE OR REPLACE VIEW job_statistics AS
SELECT 
    DATE(created_at) as date,
    job_type,
    status,
    COUNT(*) as job_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))/60) as avg_duration_minutes,
    SUM(cost_usd) as total_cost_usd
FROM gpu_jobs 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), job_type, status
ORDER BY date DESC, job_type, status;

-- Create a view for provider performance
CREATE OR REPLACE VIEW provider_performance AS
SELECT 
    provider,
    DATE(created_at) as date,
    COUNT(*) as instance_count,
    AVG(EXTRACT(EPOCH FROM (started_at - created_at))/60) as avg_startup_minutes,
    AVG(hourly_cost_usd) as avg_hourly_cost,
    SUM(total_cost_usd) as total_cost_usd
FROM gpu_instances 
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY provider, DATE(created_at)
ORDER BY date DESC, provider;

-- Create a view for resource utilization
CREATE OR REPLACE VIEW resource_utilization AS
SELECT 
    gpu_type,
    provider,
    COUNT(*) as total_instances,
    COUNT(CASE WHEN status = 'running' THEN 1 END) as running_instances,
    AVG(CASE WHEN status = 'running' THEN 
        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at))/3600 
        ELSE NULL END) as avg_runtime_hours,
    SUM(total_cost_usd) as total_cost_usd
FROM gpu_instances 
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY gpu_type, provider
ORDER BY total_instances DESC;

-- Insert some initial configuration data
-- This will be handled by the application, but we can add some defaults here

-- Create a user for monitoring (optional)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gpu_monitor') THEN
        CREATE ROLE gpu_monitor WITH LOGIN PASSWORD 'monitor_password';
        GRANT CONNECT ON DATABASE gpu_orchestration TO gpu_monitor;
        GRANT USAGE ON SCHEMA public TO gpu_monitor;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO gpu_monitor;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO gpu_monitor;
    END IF;
END
$$;

-- Create indexes for common queries (these will supplement SQLAlchemy indexes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gpu_jobs_user_status 
    ON gpu_jobs(user_id, status) WHERE status IN ('queued', 'running');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gpu_jobs_created_at_desc 
    ON gpu_jobs(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gpu_instances_provider_status 
    ON gpu_instances(provider, status) WHERE status = 'running';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gpu_instances_created_at_desc 
    ON gpu_instances(created_at DESC);

-- Create a function to clean up old completed jobs (optional)
CREATE OR REPLACE FUNCTION cleanup_old_jobs(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM gpu_jobs 
    WHERE status IN ('completed', 'failed', 'cancelled') 
    AND completed_at < CURRENT_DATE - INTERVAL '1 day' * retention_days;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RAISE NOTICE 'Cleaned up % old jobs', deleted_count;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get queue statistics
CREATE OR REPLACE FUNCTION get_queue_stats()
RETURNS TABLE(
    total_queued INTEGER,
    total_running INTEGER,
    avg_wait_time_minutes DECIMAL,
    oldest_queued_job_age_minutes DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(CASE WHEN status = 'queued' THEN 1 END)::INTEGER as total_queued,
        COUNT(CASE WHEN status = 'running' THEN 1 END)::INTEGER as total_running,
        AVG(CASE WHEN status = 'running' AND started_at IS NOT NULL THEN 
            EXTRACT(EPOCH FROM (started_at - created_at))/60 
            ELSE NULL END)::DECIMAL as avg_wait_time_minutes,
        MAX(CASE WHEN status = 'queued' THEN 
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - created_at))/60 
            ELSE NULL END)::DECIMAL as oldest_queued_job_age_minutes
    FROM gpu_jobs
    WHERE status IN ('queued', 'running');
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE gpu_orchestration TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'AIMA GPU Orchestration Database initialized successfully at %', CURRENT_TIMESTAMP;
END
$$;