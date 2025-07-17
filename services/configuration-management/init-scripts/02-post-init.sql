-- Post-initialization script for AIMA Configuration Management Service
-- This script creates views and additional database objects after tables are created

-- Create a view for configuration statistics
CREATE OR REPLACE VIEW configuration_stats AS
SELECT 
    COUNT(*) as total_configurations,
    COUNT(CASE WHEN is_sensitive THEN 1 END) as sensitive_configurations,
    COUNT(CASE WHEN is_readonly THEN 1 END) as readonly_configurations,
    COUNT(CASE WHEN category = 'system' THEN 1 END) as system_configurations,
    COUNT(CASE WHEN category = 'security' THEN 1 END) as security_configurations,
    COUNT(CASE WHEN category = 'performance' THEN 1 END) as performance_configurations,
    COUNT(CASE WHEN data_type = 'string' THEN 1 END) as string_configurations,
    COUNT(CASE WHEN data_type = 'integer' THEN 1 END) as integer_configurations,
    COUNT(CASE WHEN data_type = 'boolean' THEN 1 END) as boolean_configurations,
    COUNT(CASE WHEN data_type = 'json' THEN 1 END) as json_configurations,
    MAX(updated_at) as last_update,
    MIN(created_at) as first_created
FROM configuration_items
WHERE deleted_at IS NULL;

-- Create a view for recent configuration changes
CREATE OR REPLACE VIEW recent_configuration_changes AS
SELECT 
    ch.id,
    ch.configuration_key,
    ch.change_type,
    ch.old_value,
    ch.new_value,
    ch.changed_by,
    ch.change_reason,
    ch.changed_at,
    ci.category,
    ci.data_type,
    ci.description
FROM configuration_history ch
LEFT JOIN configuration_items ci ON ch.configuration_key = ci.key
ORDER BY ch.changed_at DESC
LIMIT 100;

-- Create useful indexes for performance
CREATE INDEX IF NOT EXISTS idx_config_items_category ON configuration_items(category);
CREATE INDEX IF NOT EXISTS idx_config_items_data_type ON configuration_items(data_type);
CREATE INDEX IF NOT EXISTS idx_config_items_updated_at ON configuration_items(updated_at);
CREATE INDEX IF NOT EXISTS idx_config_items_is_sensitive ON configuration_items(is_sensitive);
CREATE INDEX IF NOT EXISTS idx_config_items_deleted_at ON configuration_items(deleted_at);

CREATE INDEX IF NOT EXISTS idx_config_history_key ON configuration_history(configuration_key);
CREATE INDEX IF NOT EXISTS idx_config_history_changed_at ON configuration_history(changed_at);
CREATE INDEX IF NOT EXISTS idx_config_history_change_type ON configuration_history(change_type);

CREATE INDEX IF NOT EXISTS idx_config_templates_category ON configuration_templates(category);
CREATE INDEX IF NOT EXISTS idx_config_templates_data_type ON configuration_templates(data_type);

CREATE INDEX IF NOT EXISTS idx_config_locks_key ON configuration_locks(configuration_key);
CREATE INDEX IF NOT EXISTS idx_config_locks_expires_at ON configuration_locks(expires_at);

-- Post-initialization completed
SELECT 'Post-initialization completed successfully' as message;