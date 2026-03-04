# Пример скрипта для резервного копирования данных и исходников в облако (S3)

#!/bin/bash
# Требуется awscli: pip install awscli
# Настройте AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION

BACKUP_DIR="/workspaces/v1-3/999/backups"
BUCKET="argos-backups"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Локальный бэкап
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/argos_backup_$DATE.tar.gz" -C "/workspaces/v1-3/999" .

# Загрузка в S3
aws s3 cp "$BACKUP_DIR/argos_backup_$DATE.tar.gz" "s3://$BUCKET/argos_backup_$DATE.tar.gz"
echo "Backup загружен в S3: s3://$BUCKET/argos_backup_$DATE.tar.gz"
