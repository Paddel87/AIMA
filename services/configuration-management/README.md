# AIMA Configuration Management Service

The Configuration Management Service is a core component of the AIMA (AI Media Analysis) system that provides centralized configuration management with versioning, caching, and secure access control.

## Features

- **Centralized Configuration Storage**: Store all system configurations in a single, organized location
- **Hierarchical Organization**: Organize configurations by categories (system, security, performance, etc.)
- **Data Type Validation**: Support for string, integer, float, boolean, JSON, and array data types
- **Version Control**: Complete audit trail of all configuration changes
- **Secure Access**: JWT-based authentication with role-based access control
- **Caching**: Redis-based caching for high-performance configuration retrieval
- **Bulk Operations**: Update multiple configurations in a single transaction
- **Health Monitoring**: Comprehensive health checks and metrics
- **RESTful API**: Clean, well-documented REST API

## Architecture

### Components

- **FastAPI Application**: Modern, fast web framework with automatic API documentation
- **PostgreSQL Database**: Reliable storage for configuration data and history
- **Redis Cache**: High-performance caching layer for frequently accessed configurations
- **SQLAlchemy ORM**: Database abstraction and migration management
- **Pydantic Models**: Data validation and serialization

### Database Schema

- `configuration_items`: Main configuration storage
- `configuration_history`: Change tracking and audit trail
- `configuration_templates`: Predefined configuration templates
- `configuration_locks`: Concurrency control for configuration updates

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (if running without Docker)
- Redis 7+ (optional, for caching)

### Using Docker Compose (Recommended)

1. **Start the service with dependencies**:
   ```bash
   docker-compose up -d
   ```

2. **Start with management tools** (pgAdmin, Redis Commander):
   ```bash
   docker-compose --profile tools up -d
   ```

3. **Check service health**:
   ```bash
   curl http://localhost:8002/health
   ```

4. **Access API documentation**:
   - Swagger UI: http://localhost:8002/docs
   - ReDoc: http://localhost:8002/redoc

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export DATABASE_URL="postgresql://config_user:config_password@localhost:5433/aima_config"
   export REDIS_URL="redis://localhost:6380/2"
   export JWT_SECRET_KEY="your-secret-key"
   ```

3. **Run the service**:
   ```bash
   python start_service.py
   ```

## API Usage

### Authentication

All API endpoints require JWT authentication. Include the token in the Authorization header:

```bash
Authorization: Bearer <your-jwt-token>
```

### Basic Operations

#### Get All Configurations
```bash
curl -H "Authorization: Bearer <token>" \
     http://localhost:8002/api/v1/config
```

#### Get Specific Configuration
```bash
curl -H "Authorization: Bearer <token>" \
     http://localhost:8002/api/v1/config/system.service_name
```

#### Create Configuration
```bash
curl -X POST \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "key": "app.feature_flag",
       "value": "true",
       "data_type": "boolean",
       "category": "system",
       "description": "Enable new feature"
     }' \
     http://localhost:8002/api/v1/config
```

#### Update Configuration
```bash
curl -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "value": "false",
       "change_reason": "Disabling feature for maintenance"
     }' \
     http://localhost:8002/api/v1/config/app.feature_flag
```

#### Get Configuration History
```bash
curl -H "Authorization: Bearer <token>" \
     http://localhost:8002/api/v1/config/app.feature_flag/history
```

### Advanced Features

#### Bulk Updates
```bash
curl -X POST \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{
       "configurations": [
         {"key": "config1", "value": "value1"},
         {"key": "config2", "value": "value2"}
       ],
       "change_reason": "Bulk configuration update"
     }' \
     http://localhost:8002/api/v1/config/bulk
```

#### Filtering and Pagination
```bash
curl -H "Authorization: Bearer <token>" \
     "http://localhost:8002/api/v1/config?category=system&limit=10&offset=0"
```

## Configuration Categories

- **system**: Core system configurations
- **database**: Database-related settings
- **security**: Security and authentication settings
- **performance**: Performance tuning parameters
- **integration**: External service integration settings
- **ui**: User interface configurations
- **other**: Miscellaneous configurations

## Data Types

- **string**: Text values
- **integer**: Whole numbers
- **float**: Decimal numbers
- **boolean**: True/false values
- **json**: JSON objects
- **array**: JSON arrays

## Environment Variables

### Application Settings
- `APP_NAME`: Application name (default: "AIMA Configuration Management")
- `APP_VERSION`: Application version (default: "1.0.0")
- `ENVIRONMENT`: Environment (development/staging/production)
- `HOST`: Server host (default: "0.0.0.0")
- `PORT`: Server port (default: 8002)

### Database Settings
- `DATABASE_URL`: PostgreSQL connection URL
- `DATABASE_POOL_SIZE`: Connection pool size (default: 10)
- `DATABASE_MAX_OVERFLOW`: Max overflow connections (default: 20)

### Redis Settings
- `REDIS_URL`: Redis connection URL
- `REDIS_PASSWORD`: Redis password (optional)
- `REDIS_DB`: Redis database number (default: 2)
- `REDIS_MAX_CONNECTIONS`: Max Redis connections (default: 10)

### Security Settings
- `JWT_SECRET_KEY`: JWT signing secret (required)
- `JWT_ALGORITHM`: JWT algorithm (default: "HS256")
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration (default: 30)

### Service Integration
- `USER_MANAGEMENT_URL`: User management service URL

### CORS and Security
- `CORS_ORIGINS`: Allowed CORS origins (JSON array)
- `TRUSTED_HOSTS`: Trusted host names (JSON array)

### Logging
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR)
- `LOG_FORMAT`: Log format (simple/detailed)

### Configuration Management Specific
- `CONFIG_CACHE_TTL`: Cache TTL in seconds (default: 3600)
- `CONFIG_MAX_HISTORY_ENTRIES`: Max history entries per config (default: 100)
- `CONFIG_ENABLE_VERSIONING`: Enable versioning (default: true)
- `CONFIG_BACKUP_ENABLED`: Enable backups (default: true)
- `CONFIG_BACKUP_INTERVAL`: Backup interval in seconds (default: 3600)

## Health Checks

### Endpoints
- `/health`: Comprehensive health check
- `/health/ready`: Readiness check for Kubernetes
- `/health/live`: Liveness check for Kubernetes
- `/metrics`: Service metrics (admin only)

### Health Check Response
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database connection successful"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connection successful"
    },
    "configuration_service": {
      "status": "healthy",
      "message": "Configuration service operational"
    }
  }
}
```

## Monitoring and Metrics

The service provides comprehensive metrics for monitoring:

- Configuration counts by category
- Sensitive and read-only configuration counts
- Recent change statistics
- Database connection metrics
- Redis performance metrics
- Service uptime and health status

## Security

### Authentication
- JWT-based authentication
- Integration with User Management Service
- Token validation and refresh

### Authorization
- Role-based access control
- Admin-only operations for sensitive configurations
- Read-only access for regular users

### Data Protection
- Sensitive configuration masking
- Encrypted storage for sensitive values
- Audit trail for all changes

## Development

### Project Structure
```
services/configuration-management/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── config.py      # Configuration endpoints
│   │   │   └── health.py      # Health check endpoints
│   │   └── dependencies.py    # Dependency injection
│   ├── core/
│   │   ├── config.py         # Application configuration
│   │   ├── database.py       # Database management
│   │   └── redis.py          # Redis management
│   ├── models/
│   │   ├── database.py       # SQLAlchemy models
│   │   └── schemas.py        # Pydantic schemas
│   ├── services/
│   │   └── config_service.py # Business logic
│   └── main.py              # FastAPI application
├── init-scripts/
│   └── 01-init-database.sql # Database initialization
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── start_service.py         # Service startup script
└── README.md
```

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Deployment

### Docker
```bash
# Build image
docker build -t aima-configuration-management .

# Run container
docker run -p 8002:8002 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -e REDIS_URL="redis://host:6379/2" \
  -e JWT_SECRET_KEY="your-secret" \
  aima-configuration-management
```

### Kubernetes
See the main AIMA deployment documentation for Kubernetes manifests.

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check DATABASE_URL format
   - Verify database is running and accessible
   - Check network connectivity

2. **Redis Connection Failed**
   - Verify REDIS_URL format
   - Check if Redis is running
   - Service will work without Redis (degraded performance)

3. **Authentication Errors**
   - Verify JWT_SECRET_KEY is set
   - Check token format and expiration
   - Ensure User Management Service is accessible

4. **Permission Denied**
   - Check user role and permissions
   - Admin role required for most operations
   - Verify JWT token contains correct role information

### Logs

Logs are written to:
- Console (stdout)
- File: `logs/config_service.log`

Increase log level for debugging:
```bash
export LOG_LEVEL=DEBUG
```

## Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Ensure all health checks pass
5. Test with both PostgreSQL and Redis

## License

This project is part of the AIMA system. See the main project license for details.