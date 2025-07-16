# AIMA User Management Service

The User Management Service is a core component of the AIMA (AI Media Analysis) system, responsible for user authentication, authorization, session management, and user profile administration.

## Features

### Authentication & Authorization
- JWT-based authentication with access and refresh tokens
- Role-based access control (RBAC) with hierarchical permissions
- Session management with Redis backend
- Password strength validation and secure hashing
- Account lockout protection against brute force attacks

### User Management
- User registration and profile management
- Admin user management with CRUD operations
- User status management (active, suspended, pending)
- Audit logging for all user actions
- Comprehensive user statistics and reporting

### Security Features
- Secure password hashing with bcrypt
- JWT token management with configurable expiration
- Rate limiting to prevent abuse
- CORS configuration for web applications
- Input validation and sanitization

### Monitoring & Health Checks
- Comprehensive health check endpoints
- Prometheus metrics integration
- Structured logging with correlation IDs
- Database and Redis connectivity monitoring

## Architecture

### Technology Stack
- **Framework**: FastAPI with Uvicorn ASGI server
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache/Sessions**: Redis
- **Message Queue**: RabbitMQ
- **Monitoring**: Prometheus metrics
- **Logging**: Structured logging with structlog

### Project Structure
```
user-management/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py          # Authentication endpoints
│   │   │   ├── users.py         # User management endpoints
│   │   │   ├── health.py        # Health check endpoints
│   │   │   └── __init__.py
│   │   ├── dependencies.py      # API dependencies
│   │   └── __init__.py
│   ├── core/
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database models and connection
│   │   ├── redis.py            # Redis connection and session management
│   │   ├── messaging.py        # RabbitMQ messaging
│   │   ├── security.py         # Security utilities
│   │   └── exceptions.py       # Custom exceptions
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   ├── services/
│   │   └── user_service.py     # Business logic
│   └── main.py                 # FastAPI application
├── alembic/                    # Database migrations
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
├── .env.example               # Environment variables template
└── README.md                  # This file
```

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Redis 6+
- RabbitMQ 3.8+

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd aima/services/user-management
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the service**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Deployment

1. **Build the image**
   ```bash
   docker build -t aima/user-management .
   ```

2. **Run with Docker Compose** (from project root)
   ```bash
   docker-compose up user-management
   ```

## API Documentation

Once the service is running, you can access:
- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc documentation**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - User logout
- `POST /api/v1/auth/change-password` - Change password
- `POST /api/v1/auth/reset-password` - Request password reset

#### User Management
- `GET /api/v1/users/` - List users (admin)
- `POST /api/v1/users/` - Create user (admin)
- `GET /api/v1/users/{user_id}` - Get user details
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user (admin)

#### Health Checks
- `GET /api/v1/health/` - Basic health check
- `GET /api/v1/health/ready` - Readiness probe
- `GET /api/v1/health/live` - Liveness probe
- `GET /api/v1/health/detailed` - Detailed health status

## Configuration

### Environment Variables

Key configuration options (see `.env.example` for complete list):

```bash
# Application
APP_NAME=AIMA User Management Service
ENVIRONMENT=development
DEBUG=true

# Security
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=aima_users
DATABASE_USER=aima_user
DATABASE_PASSWORD=your-password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# RabbitMQ
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=aima
RABBITMQ_PASSWORD=your-password
```

### Database Schema

The service uses the following main tables:
- `users` - User accounts and profiles
- `user_sessions` - Active user sessions
- `audit_logs` - User action audit trail

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# Run with coverage
pytest --cov=app
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

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Monitoring

### Health Checks
The service provides multiple health check endpoints for different monitoring needs:
- Basic health check for load balancers
- Readiness check for Kubernetes
- Detailed health check for comprehensive monitoring

### Metrics
Prometheus metrics are available at `/metrics` endpoint, including:
- Request counts and latencies
- Database connection pool status
- Redis connection status
- Custom business metrics

### Logging
Structured logging with correlation IDs for request tracing:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "app.api.v1.auth",
  "message": "User login successful",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "correlation_id": "req_abc123"
}
```

## Security Considerations

### Authentication
- JWT tokens with configurable expiration
- Refresh token rotation
- Session invalidation on logout

### Password Security
- Bcrypt hashing with configurable rounds
- Password strength validation
- Account lockout after failed attempts

### API Security
- Rate limiting per endpoint
- CORS configuration
- Input validation and sanitization
- SQL injection prevention with ORM

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL is running
   - Verify connection parameters in `.env`
   - Ensure database exists and user has permissions

2. **Redis Connection Failed**
   - Check Redis is running
   - Verify Redis configuration
   - Check network connectivity

3. **JWT Token Issues**
   - Verify JWT_SECRET_KEY is set
   - Check token expiration settings
   - Ensure system time is synchronized

### Logs
Check application logs for detailed error information:
```bash
# Docker logs
docker logs aima-user-management

# Local development
tail -f logs/user-management.log
```

## Contributing

1. Follow the existing code style and patterns
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all health checks pass
5. Follow semantic versioning for releases

## License

This project is part of the AIMA system. See the main project LICENSE file for details.