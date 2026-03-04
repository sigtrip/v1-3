#!/bin/bash
# Автоматическое резервное копирование исходников и данных ARGOS

BACKUP_DIR="/workspaces/v1-3/999/backups"
SRC_DIR="/workspaces/v1-3/999"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/argos_backup_$DATE.tar.gz" -C "$SRC_DIR" .
echo "Backup создан: $BACKUP_DIR/argos_backup_$DATE.tar.gz"
