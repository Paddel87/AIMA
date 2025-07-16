-- AIMA System Database Schema Initialization
-- This script creates the core database schema for the AIMA system

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- User sessions table
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

-- System configuration table
CREATE TABLE system_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(255) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    is_sensitive BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id)
);

-- Media files table
CREATE TABLE media_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_id VARCHAR(255) UNIQUE NOT NULL, -- Global unique identifier
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- video, audio, image
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    duration_seconds DECIMAL(10,3), -- for video/audio
    resolution VARCHAR(20), -- for video/image (e.g., "1920x1080")
    fps DECIMAL(5,2), -- for video
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for deduplication
    storage_provider VARCHAR(50) NOT NULL, -- minio, s3, local
    storage_bucket VARCHAR(255),
    storage_path VARCHAR(500) NOT NULL,
    upload_status VARCHAR(50) DEFAULT 'pending', -- pending, uploading, completed, failed
    processing_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    uploaded_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analysis jobs table
CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) UNIQUE NOT NULL, -- Global unique identifier
    media_id UUID NOT NULL REFERENCES media_files(id) ON DELETE CASCADE,
    job_type VARCHAR(100) NOT NULL, -- image_analysis, video_analysis, audio_analysis, data_fusion
    job_status VARCHAR(50) DEFAULT 'pending', -- pending, queued, running, completed, failed, cancelled
    priority INTEGER DEFAULT 5, -- 1 (highest) to 10 (lowest)
    configuration JSONB, -- Job-specific configuration
    estimated_cost_cents INTEGER, -- Estimated cost in cents
    actual_cost_cents INTEGER, -- Actual cost in cents
    gpu_instance_id VARCHAR(255), -- Reference to GPU instance
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- GPU instances table
CREATE TABLE gpu_instances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    instance_id VARCHAR(255) UNIQUE NOT NULL, -- Provider-specific instance ID
    provider VARCHAR(50) NOT NULL, -- runpod, vast_ai, local, aws, gcp
    instance_type VARCHAR(100) NOT NULL, -- e.g., "RTX 4090", "A100"
    gpu_count INTEGER NOT NULL DEFAULT 1,
    memory_gb INTEGER,
    vcpus INTEGER,
    storage_gb INTEGER,
    hourly_cost_cents INTEGER, -- Cost per hour in cents
    region VARCHAR(100),
    status VARCHAR(50) NOT NULL, -- creating, running, stopping, stopped, terminated, error
    external_ip VARCHAR(45), -- IPv4 or IPv6
    internal_ip VARCHAR(45),
    ssh_port INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    terminated_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat TIMESTAMP WITH TIME ZONE
);

-- Job assignments to GPU instances
CREATE TABLE job_gpu_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    gpu_instance_id UUID NOT NULL REFERENCES gpu_instances(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'assigned' -- assigned, running, completed, failed
);

-- System metrics table
CREATE TABLE system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15,6) NOT NULL,
    metric_unit VARCHAR(50),
    tags JSONB, -- Additional metadata
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit log table
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_user_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_system_config_key ON system_config(config_key);
CREATE INDEX idx_media_files_media_id ON media_files(media_id);
CREATE INDEX idx_media_files_hash ON media_files(file_hash);
CREATE INDEX idx_media_files_uploaded_by ON media_files(uploaded_by);
CREATE INDEX idx_analysis_jobs_job_id ON analysis_jobs(job_id);
CREATE INDEX idx_analysis_jobs_media_id ON analysis_jobs(media_id);
CREATE INDEX idx_analysis_jobs_status ON analysis_jobs(job_status);
CREATE INDEX idx_analysis_jobs_priority ON analysis_jobs(priority);
CREATE INDEX idx_gpu_instances_instance_id ON gpu_instances(instance_id);
CREATE INDEX idx_gpu_instances_provider ON gpu_instances(provider);
CREATE INDEX idx_gpu_instances_status ON gpu_instances(status);
CREATE INDEX idx_job_gpu_assignments_job_id ON job_gpu_assignments(job_id);
CREATE INDEX idx_job_gpu_assignments_gpu_instance_id ON job_gpu_assignments(gpu_instance_id);
CREATE INDEX idx_system_metrics_name_timestamp ON system_metrics(metric_name, timestamp);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_config_updated_at BEFORE UPDATE ON system_config
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON media_files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_jobs_updated_at BEFORE UPDATE ON analysis_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();