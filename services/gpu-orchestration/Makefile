# AIMA GPU Orchestration Service - Makefile
# This Makefile provides convenient commands for development, testing, and deployment

# =============================================================================
# CONFIGURATION
# =============================================================================

# Project configuration
PROJECT_NAME := gpu-orchestration
PROJECT_VERSION := 1.0.0
DOCKER_REGISTRY := docker.io
DOCKER_REPOSITORY := aima/gpu-orchestration
DOCKER_TAG := latest

# Python configuration
PYTHON := python
PIP := pip
PYTEST := pytest
BLACK := black
ISORT := isort
FLAKE8 := flake8
MYPY := mypy
BANDIT := bandit

# Docker configuration
DOCKER := docker
DOCKER_COMPOSE := docker-compose
DOCKERFILE := Dockerfile
COMPOSE_FILE := docker-compose.yml

# Environment
ENV_FILE := .env
ENV_EXAMPLE := .env.example

# Directories
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs
COVERAGE_DIR := htmlcov
DIST_DIR := dist
BUILD_DIR := build

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
MAGENTA := \033[35m
CYAN := \033[36m
WHITE := \033[37m
RESET := \033[0m

# =============================================================================
# DEFAULT TARGET
# =============================================================================

.DEFAULT_GOAL := help

# =============================================================================
# HELP
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo "$(CYAN)AIMA GPU Orchestration Service - Available Commands$(RESET)"
	@echo ""
	@echo "$(YELLOW)Development:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "(install|setup|dev|run|test|lint|format|clean)"
	@echo ""
	@echo "$(YELLOW)Docker:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "(build|push|pull|up|down|logs|shell)"
	@echo ""
	@echo "$(YELLOW)Database:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "(db-|migrate|seed)"
	@echo ""
	@echo "$(YELLOW)Deployment:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "(deploy|release|k8s)"
	@echo ""
	@echo "$(YELLOW)Utilities:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | grep -E "(backup|restore|monitor|security)"

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

.PHONY: install
install: ## Install all dependencies
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	$(PIP) install -e .
	$(PIP) install -e ".[dev,test,docs]"
	@echo "$(GREEN)Dependencies installed successfully!$(RESET)"

.PHONY: install-dev
install-dev: ## Install development dependencies only
	@echo "$(BLUE)Installing development dependencies...$(RESET)"
	$(PIP) install -e ".[dev]"
	@echo "$(GREEN)Development dependencies installed!$(RESET)"

.PHONY: install-test
install-test: ## Install testing dependencies only
	@echo "$(BLUE)Installing testing dependencies...$(RESET)"
	$(PIP) install -e ".[test]"
	@echo "$(GREEN)Testing dependencies installed!$(RESET)"

.PHONY: setup
setup: ## Initial project setup
	@echo "$(BLUE)Setting up project...$(RESET)"
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "$(YELLOW)Creating .env file from template...$(RESET)"; \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "$(GREEN).env file created! Please update it with your configuration.$(RESET)"; \
	else \
		echo "$(YELLOW).env file already exists.$(RESET)"; \
	fi
	$(MAKE) install
	$(MAKE) pre-commit-install
	@echo "$(GREEN)Project setup completed!$(RESET)"

.PHONY: pre-commit-install
pre-commit-install: ## Install pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(RESET)"
	pre-commit install
	@echo "$(GREEN)Pre-commit hooks installed!$(RESET)"

# =============================================================================
# DEVELOPMENT
# =============================================================================

.PHONY: dev
dev: ## Start development server with auto-reload
	@echo "$(BLUE)Starting development server...$(RESET)"
	uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: dev-worker
dev-worker: ## Start Celery worker for development
	@echo "$(BLUE)Starting Celery worker...$(RESET)"
	celery -A src.core.celery worker --loglevel=info --concurrency=4

.PHONY: dev-beat
dev-beat: ## Start Celery beat scheduler for development
	@echo "$(BLUE)Starting Celery beat scheduler...$(RESET)"
	celery -A src.core.celery beat --loglevel=info

.PHONY: dev-flower
dev-flower: ## Start Flower for Celery monitoring
	@echo "$(BLUE)Starting Flower...$(RESET)"
	celery -A src.core.celery flower --port=5555

.PHONY: run
run: ## Run the application in production mode
	@echo "$(BLUE)Starting application...$(RESET)"
	gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test: ## Run all tests
	@echo "$(BLUE)Running tests...$(RESET)"
	$(PYTEST) $(TEST_DIR) -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)Tests completed! Coverage report available in $(COVERAGE_DIR)/$(RESET)"

.PHONY: test-unit
test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/integration -v

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests
	@echo "$(BLUE)Running end-to-end tests...$(RESET)"
	$(PYTEST) $(TEST_DIR)/e2e -v

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	@echo "$(BLUE)Running tests in watch mode...$(RESET)"
	$(PYTEST) $(TEST_DIR) -v --cov=src -f

.PHONY: test-coverage
test-coverage: ## Generate test coverage report
	@echo "$(BLUE)Generating coverage report...$(RESET)"
	$(PYTEST) $(TEST_DIR) --cov=src --cov-report=html --cov-report=term
	@echo "$(GREEN)Coverage report generated in $(COVERAGE_DIR)/$(RESET)"

# =============================================================================
# CODE QUALITY
# =============================================================================

.PHONY: lint
lint: ## Run all linting tools
	@echo "$(BLUE)Running linting tools...$(RESET)"
	$(MAKE) lint-black
	$(MAKE) lint-isort
	$(MAKE) lint-flake8
	$(MAKE) lint-mypy
	@echo "$(GREEN)Linting completed!$(RESET)"

.PHONY: lint-black
lint-black: ## Check code formatting with Black
	@echo "$(BLUE)Checking code formatting with Black...$(RESET)"
	$(BLACK) --check --diff $(SRC_DIR) $(TEST_DIR)

.PHONY: lint-isort
lint-isort: ## Check import sorting with isort
	@echo "$(BLUE)Checking import sorting with isort...$(RESET)"
	$(ISORT) --check-only --diff $(SRC_DIR) $(TEST_DIR)

.PHONY: lint-flake8
lint-flake8: ## Check code style with flake8
	@echo "$(BLUE)Checking code style with flake8...$(RESET)"
	$(FLAKE8) $(SRC_DIR) $(TEST_DIR)

.PHONY: lint-mypy
lint-mypy: ## Check type hints with mypy
	@echo "$(BLUE)Checking type hints with mypy...$(RESET)"
	$(MYPY) $(SRC_DIR)

.PHONY: format
format: ## Format code with Black and isort
	@echo "$(BLUE)Formatting code...$(RESET)"
	$(BLACK) $(SRC_DIR) $(TEST_DIR)
	$(ISORT) $(SRC_DIR) $(TEST_DIR)
	@echo "$(GREEN)Code formatted!$(RESET)"

.PHONY: security
security: ## Run security checks with bandit
	@echo "$(BLUE)Running security checks...$(RESET)"
	$(BANDIT) -r $(SRC_DIR) -f json -o bandit-report.json
	$(BANDIT) -r $(SRC_DIR)
	@echo "$(GREEN)Security checks completed!$(RESET)"

# =============================================================================
# DOCKER
# =============================================================================

.PHONY: build
build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(RESET)"
	$(DOCKER) build -t $(DOCKER_REPOSITORY):$(DOCKER_TAG) .
	@echo "$(GREEN)Docker image built: $(DOCKER_REPOSITORY):$(DOCKER_TAG)$(RESET)"

.PHONY: build-dev
build-dev: ## Build Docker image for development
	@echo "$(BLUE)Building development Docker image...$(RESET)"
	$(DOCKER) build --target development -t $(DOCKER_REPOSITORY):dev .
	@echo "$(GREEN)Development Docker image built: $(DOCKER_REPOSITORY):dev$(RESET)"

.PHONY: build-prod
build-prod: ## Build Docker image for production
	@echo "$(BLUE)Building production Docker image...$(RESET)"
	$(DOCKER) build --target production-optimized -t $(DOCKER_REPOSITORY):prod .
	@echo "$(GREEN)Production Docker image built: $(DOCKER_REPOSITORY):prod$(RESET)"

.PHONY: push
push: ## Push Docker image to registry
	@echo "$(BLUE)Pushing Docker image...$(RESET)"
	$(DOCKER) push $(DOCKER_REPOSITORY):$(DOCKER_TAG)
	@echo "$(GREEN)Docker image pushed!$(RESET)"

.PHONY: pull
pull: ## Pull Docker image from registry
	@echo "$(BLUE)Pulling Docker image...$(RESET)"
	$(DOCKER) pull $(DOCKER_REPOSITORY):$(DOCKER_TAG)
	@echo "$(GREEN)Docker image pulled!$(RESET)"

.PHONY: up
up: ## Start all services with Docker Compose
	@echo "$(BLUE)Starting services...$(RESET)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Services started!$(RESET)"

.PHONY: up-dev
up-dev: ## Start services in development mode
	@echo "$(BLUE)Starting development services...$(RESET)"
	$(DOCKER_COMPOSE) --profile development up -d
	@echo "$(GREEN)Development services started!$(RESET)"

.PHONY: down
down: ## Stop all services
	@echo "$(BLUE)Stopping services...$(RESET)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Services stopped!$(RESET)"

.PHONY: restart
restart: ## Restart all services
	@echo "$(BLUE)Restarting services...$(RESET)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)Services restarted!$(RESET)"

.PHONY: logs
logs: ## Show logs from all services
	$(DOCKER_COMPOSE) logs -f

.PHONY: logs-app
logs-app: ## Show logs from main application
	$(DOCKER_COMPOSE) logs -f gpu-orchestration

.PHONY: shell
shell: ## Open shell in running container
	$(DOCKER_COMPOSE) exec gpu-orchestration /bin/bash

.PHONY: shell-db
shell-db: ## Open PostgreSQL shell
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d gpu_orchestration

.PHONY: shell-redis
shell-redis: ## Open Redis shell
	$(DOCKER_COMPOSE) exec redis redis-cli

# =============================================================================
# DATABASE
# =============================================================================

.PHONY: db-init
db-init: ## Initialize database
	@echo "$(BLUE)Initializing database...$(RESET)"
	alembic upgrade head
	@echo "$(GREEN)Database initialized!$(RESET)"

.PHONY: db-migrate
db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(RESET)"
	alembic upgrade head
	@echo "$(GREEN)Database migrations completed!$(RESET)"

.PHONY: db-migration
db-migration: ## Create new database migration
	@echo "$(BLUE)Creating new migration...$(RESET)"
	@read -p "Migration message: " message; \
	alembic revision --autogenerate -m "$$message"
	@echo "$(GREEN)Migration created!$(RESET)"

.PHONY: db-downgrade
db-downgrade: ## Downgrade database by one revision
	@echo "$(BLUE)Downgrading database...$(RESET)"
	alembic downgrade -1
	@echo "$(GREEN)Database downgraded!$(RESET)"

.PHONY: db-reset
db-reset: ## Reset database (WARNING: This will delete all data)
	@echo "$(RED)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		alembic downgrade base; \
		alembic upgrade head; \
		echo "$(GREEN)Database reset completed!$(RESET)"; \
	else \
		echo "$(YELLOW)Database reset cancelled.$(RESET)"; \
	fi

.PHONY: db-seed
db-seed: ## Seed database with sample data
	@echo "$(BLUE)Seeding database...$(RESET)"
	$(PYTHON) scripts/seed_database.py
	@echo "$(GREEN)Database seeded!$(RESET)"

.PHONY: db-backup
db-backup: ## Create database backup
	@echo "$(BLUE)Creating database backup...$(RESET)"
	$(DOCKER_COMPOSE) exec postgres pg_dump -U postgres gpu_orchestration > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backup created!$(RESET)"

.PHONY: db-restore
db-restore: ## Restore database from backup
	@echo "$(BLUE)Restoring database...$(RESET)"
	@read -p "Backup file path: " backup_file; \
	$(DOCKER_COMPOSE) exec -T postgres psql -U postgres gpu_orchestration < "$$backup_file"
	@echo "$(GREEN)Database restored!$(RESET)"

# =============================================================================
# MONITORING
# =============================================================================

.PHONY: monitor
monitor: ## Open monitoring dashboard
	@echo "$(BLUE)Opening monitoring dashboard...$(RESET)"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Flower: http://localhost:5555"
	@echo "Jaeger: http://localhost:16686"

.PHONY: metrics
metrics: ## Show application metrics
	@echo "$(BLUE)Fetching application metrics...$(RESET)"
	curl -s http://localhost:8000/metrics

.PHONY: health
health: ## Check application health
	@echo "$(BLUE)Checking application health...$(RESET)"
	curl -s http://localhost:8000/health | jq .

# =============================================================================
# DEPLOYMENT
# =============================================================================

.PHONY: deploy-dev
deploy-dev: ## Deploy to development environment
	@echo "$(BLUE)Deploying to development...$(RESET)"
	$(MAKE) build-dev
	$(MAKE) up-dev
	@echo "$(GREEN)Deployed to development!$(RESET)"

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging environment
	@echo "$(BLUE)Deploying to staging...$(RESET)"
	$(MAKE) build-prod
	$(MAKE) push
	# Add staging deployment commands here
	@echo "$(GREEN)Deployed to staging!$(RESET)"

.PHONY: deploy-prod
deploy-prod: ## Deploy to production environment
	@echo "$(BLUE)Deploying to production...$(RESET)"
	@echo "$(RED)WARNING: This will deploy to production!$(RESET)"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(MAKE) build-prod; \
		$(MAKE) push; \
		echo "$(GREEN)Deployed to production!$(RESET)"; \
	else \
		echo "$(YELLOW)Production deployment cancelled.$(RESET)"; \
	fi

.PHONY: k8s-deploy
k8s-deploy: ## Deploy to Kubernetes
	@echo "$(BLUE)Deploying to Kubernetes...$(RESET)"
	kubectl apply -f k8s/
	@echo "$(GREEN)Deployed to Kubernetes!$(RESET)"

.PHONY: k8s-delete
k8s-delete: ## Delete from Kubernetes
	@echo "$(BLUE)Deleting from Kubernetes...$(RESET)"
	kubectl delete -f k8s/
	@echo "$(GREEN)Deleted from Kubernetes!$(RESET)"

.PHONY: release
release: ## Create a new release
	@echo "$(BLUE)Creating new release...$(RESET)"
	@read -p "Release version (current: $(PROJECT_VERSION)): " version; \
	if [ -n "$$version" ]; then \
		echo "Creating release $$version..."; \
		git tag -a "v$$version" -m "Release v$$version"; \
		git push origin "v$$version"; \
		echo "$(GREEN)Release v$$version created!$(RESET)"; \
	else \
		echo "$(YELLOW)Release creation cancelled.$(RESET)"; \
	fi

# =============================================================================
# CLEANUP
# =============================================================================

.PHONY: clean
clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning up...$(RESET)"
	rm -rf $(BUILD_DIR) $(DIST_DIR) $(COVERAGE_DIR)
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete
	find . -type f -name "*.log" -delete
	@echo "$(GREEN)Cleanup completed!$(RESET)"

.PHONY: clean-docker
clean-docker: ## Clean up Docker resources
	@echo "$(BLUE)Cleaning up Docker resources...$(RESET)"
	$(DOCKER) system prune -f
	$(DOCKER) volume prune -f
	@echo "$(GREEN)Docker cleanup completed!$(RESET)"

.PHONY: clean-all
clean-all: clean clean-docker ## Clean up everything
	@echo "$(GREEN)Full cleanup completed!$(RESET)"

# =============================================================================
# UTILITIES
# =============================================================================

.PHONY: requirements
requirements: ## Generate requirements.txt from pyproject.toml
	@echo "$(BLUE)Generating requirements.txt...$(RESET)"
	pip-compile pyproject.toml
	@echo "$(GREEN)requirements.txt generated!$(RESET)"

.PHONY: update-deps
update-deps: ## Update all dependencies
	@echo "$(BLUE)Updating dependencies...$(RESET)"
	pip-compile --upgrade pyproject.toml
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)Dependencies updated!$(RESET)"

.PHONY: check-deps
check-deps: ## Check for dependency vulnerabilities
	@echo "$(BLUE)Checking dependencies for vulnerabilities...$(RESET)"
	safety check
	@echo "$(GREEN)Dependency check completed!$(RESET)"

.PHONY: docs
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(RESET)"
	sphinx-build -b html $(DOCS_DIR) $(DOCS_DIR)/_build/html
	@echo "$(GREEN)Documentation generated in $(DOCS_DIR)/_build/html/$(RESET)"

.PHONY: docs-serve
docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation...$(RESET)"
	cd $(DOCS_DIR)/_build/html && python -m http.server 8080

.PHONY: version
version: ## Show project version
	@echo "$(PROJECT_NAME) v$(PROJECT_VERSION)"

.PHONY: info
info: ## Show project information
	@echo "$(CYAN)Project Information:$(RESET)"
	@echo "Name: $(PROJECT_NAME)"
	@echo "Version: $(PROJECT_VERSION)"
	@echo "Docker Repository: $(DOCKER_REPOSITORY)"
	@echo "Docker Tag: $(DOCKER_TAG)"
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Docker: $(shell $(DOCKER) --version)"
	@echo "Docker Compose: $(shell $(DOCKER_COMPOSE) --version)"

# =============================================================================
# PHONY TARGETS
# =============================================================================

.PHONY: all
all: clean install lint test build ## Run full CI pipeline
	@echo "$(GREEN)Full CI pipeline completed!$(RESET)"