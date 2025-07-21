#!/bin/bash
# PostgreSQL Backup Script for AIMA System
# This script creates automated backups of the PostgreSQL database

set -e

# Configuration
DB_NAME="aima"
DB_USER="aima_user"
DB_HOST="postgres"
DB_PORT="5432"
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/aima_backup_${TIMESTAMP}.sql"
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting PostgreSQL backup..."

# Create database backup
if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --verbose \
    --clean \
    --if-exists \
    --create \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_FILE}.custom"; then
    
    echo "[$(date)] Custom format backup completed: ${BACKUP_FILE}.custom"
    
    # Also create a plain SQL backup for easier inspection
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --clean \
        --if-exists \
        --create \
        --format=plain \
        --file="${BACKUP_FILE}"
    
    echo "[$(date)] Plain SQL backup completed: ${BACKUP_FILE}"
    
    # Compress the plain SQL backup
    gzip "${BACKUP_FILE}"
    echo "[$(date)] Backup compressed: ${BACKUP_FILE}.gz"
    
    # Get backup file sizes
    CUSTOM_SIZE=$(du -h "${BACKUP_FILE}.custom" | cut -f1)
    PLAIN_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
    
    echo "[$(date)] Backup sizes - Custom: $CUSTOM_SIZE, Plain (compressed): $PLAIN_SIZE"
    
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups (keep only last N days)
echo "[$(date)] Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "aima_backup_*.sql*" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "aima_backup_*.custom" -type f -mtime +$RETENTION_DAYS -delete

# List remaining backups
echo "[$(date)] Current backups:"
ls -lh "$BACKUP_DIR"/aima_backup_* 2>/dev/null || echo "No backups found"

echo "[$(date)] Backup process completed successfully!"