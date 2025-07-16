-- AIMA System Initial Data
-- This script inserts initial data for the AIMA system

-- Insert default admin user
-- Password: admin123 (hashed with bcrypt)
INSERT INTO users (id, username, email, password_hash, first_name, last_name, role, is_active)
VALUES (
    uuid_generate_v4(),
    'admin',
    'admin@aima.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3bp.Gm.F5e', -- admin123
    'System',
    'Administrator',
    'admin',
    true
);

-- Insert default system configurations
INSERT INTO system_config (config_key, config_value, description, is_sensitive) VALUES
('system.name', '"AIMA - AI Media Analysis"', 'System display name', false),
('system.version', '"1.0.0"', 'Current system version', false),
('system.maintenance_mode', 'false', 'Enable/disable maintenance mode', false),
('system.max_upload_size_mb', '1000', 'Maximum file upload size in MB', false),
('system.supported_video_formats', '["mp4", "avi", "mov", "mkv", "webm"]', 'Supported video file formats', false),
('system.supported_audio_formats', '["mp3", "wav", "flac", "aac", "ogg"]', 'Supported audio file formats', false),
('system.supported_image_formats', '["jpg", "jpeg", "png", "bmp", "tiff", "webp"]', 'Supported image file formats', false),
('system.default_analysis_timeout_minutes', '60', 'Default timeout for analysis jobs in minutes', false),
('system.max_concurrent_jobs', '10', 'Maximum number of concurrent analysis jobs', false),
('system.job_retry_attempts', '3', 'Number of retry attempts for failed jobs', false),

-- Storage configuration
('storage.default_provider', '"minio"', 'Default storage provider', false),
('storage.minio.endpoint', '"minio:9000"', 'MinIO endpoint', false),
('storage.minio.access_key', '"aima_user"', 'MinIO access key', true),
('storage.minio.secret_key', '"aima_password"', 'MinIO secret key', true),
('storage.minio.bucket_media', '"aima-media"', 'MinIO bucket for media files', false),
('storage.minio.bucket_results', '"aima-results"', 'MinIO bucket for analysis results', false),
('storage.retention_days', '365', 'Default file retention period in days', false),

-- Database configuration
('database.mongodb.connection_string', '"mongodb://aima_user:aima_password@mongodb:27017/aima"', 'MongoDB connection string', true),
('database.redis.connection_string', '"redis://:aima_password@redis:6379/0"', 'Redis connection string', true),
('database.milvus.endpoint', '"milvus:19530"', 'Milvus endpoint', false),

-- Message broker configuration
('messaging.rabbitmq.connection_string', '"amqp://aima_user:aima_password@rabbitmq:5672/"', 'RabbitMQ connection string', true),
('messaging.default_queue_ttl_hours', '24', 'Default message TTL in hours', false),

-- GPU orchestration configuration
('gpu.providers.enabled', '["local", "runpod", "vast_ai"]', 'Enabled GPU providers', false),
('gpu.local.enabled', 'true', 'Enable local GPU usage', false),
('gpu.runpod.api_key', '""', 'RunPod API key', true),
('gpu.vast_ai.api_key', '""', 'Vast.ai API key', true),
('gpu.auto_scaling.enabled', 'true', 'Enable automatic GPU scaling', false),
('gpu.auto_scaling.min_instances', '0', 'Minimum GPU instances', false),
('gpu.auto_scaling.max_instances', '5', 'Maximum GPU instances', false),
('gpu.idle_timeout_minutes', '10', 'GPU instance idle timeout in minutes', false),

-- Analysis configuration
('analysis.video.default_fps', '30', 'Default FPS for video analysis', false),
('analysis.video.max_resolution', '"1920x1080"', 'Maximum video resolution for analysis', false),
('analysis.audio.sample_rate', '44100', 'Audio sample rate for analysis', false),
('analysis.image.max_size_mb', '50', 'Maximum image size for analysis in MB', false),
('analysis.models.face_detection', '"retinaface"', 'Default face detection model', false),
('analysis.models.object_detection', '"yolov8"', 'Default object detection model', false),
('analysis.models.speech_recognition', '"whisper"', 'Default speech recognition model', false),
('analysis.models.llm_fusion', '"llama3.1"', 'Default LLM for data fusion', false),

-- Security configuration
('security.jwt.secret_key', '"your-super-secret-jwt-key-change-this-in-production"', 'JWT secret key', true),
('security.jwt.expiration_hours', '24', 'JWT token expiration in hours', false),
('security.password.min_length', '8', 'Minimum password length', false),
('security.password.require_special_chars', 'true', 'Require special characters in passwords', false),
('security.session.timeout_hours', '8', 'Session timeout in hours', false),
('security.rate_limiting.enabled', 'true', 'Enable rate limiting', false),
('security.rate_limiting.requests_per_minute', '100', 'Maximum requests per minute per user', false),

-- Monitoring configuration
('monitoring.metrics.enabled', 'true', 'Enable metrics collection', false),
('monitoring.metrics.retention_days', '30', 'Metrics retention period in days', false),
('monitoring.alerts.enabled', 'true', 'Enable alerting', false),
('monitoring.alerts.email_notifications', 'true', 'Enable email notifications for alerts', false),

-- Cost management
('cost.tracking.enabled', 'true', 'Enable cost tracking', false),
('cost.gpu.runpod_markup_percent', '10', 'Markup percentage for RunPod costs', false),
('cost.gpu.vast_ai_markup_percent', '10', 'Markup percentage for Vast.ai costs', false),
('cost.storage.per_gb_per_month_cents', '5', 'Storage cost per GB per month in cents', false),
('cost.analysis.base_cost_cents', '10', 'Base cost per analysis in cents', false),

-- Feature flags
('features.advanced_analytics', 'true', 'Enable advanced analytics features', false),
('features.real_time_processing', 'false', 'Enable real-time processing (experimental)', false),
('features.multi_language_support', 'true', 'Enable multi-language support', false),
('features.api_v2', 'false', 'Enable API v2 (experimental)', false),
('features.mobile_app', 'false', 'Enable mobile app support', false);

-- Insert initial system metrics
INSERT INTO system_metrics (metric_name, metric_value, metric_unit, tags) VALUES
('system.startup_time', EXTRACT(EPOCH FROM CURRENT_TIMESTAMP), 'seconds', '{"component": "database"}'),
('system.version', 1.0, 'version', '{"component": "core"}'),
('database.schema_version', 1, 'version', '{"component": "database"}');

-- Log the initialization in audit log
INSERT INTO audit_log (action, resource_type, new_values) VALUES
('system_initialized', 'system', '{"timestamp": "' || CURRENT_TIMESTAMP || '", "version": "1.0.0"}');