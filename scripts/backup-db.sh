#!/usr/bin/env bash
# Daily PostgreSQL backup. Drop into cron:
#   0 3 * * *  cd /opt/yozuvchim && ./scripts/backup-db.sh >> /var/log/yozuvchim-backup.log 2>&1
#
# Backups are written to ./backups/ as yozuvchim-YYYYMMDD-HHMM.sql.gz
# Backups older than RETAIN_DAYS (default 14) are removed.

set -euo pipefail

cd "$(dirname "$0")/.."

# Load env so we know POSTGRES_USER / POSTGRES_DB
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

stamp="$(date -u +%Y%m%d-%H%M)"
out="$BACKUP_DIR/yozuvchim-$stamp.sql.gz"

echo "[$(date -u +%FT%TZ)] backup → $out"

docker compose exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip -9 > "$out"

# Retention
find "$BACKUP_DIR" -name 'yozuvchim-*.sql.gz' -type f -mtime +"$RETAIN_DAYS" -delete

echo "[$(date -u +%FT%TZ)] done. Kept latest:"
ls -lh "$BACKUP_DIR" | tail -5
