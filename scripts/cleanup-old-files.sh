#!/usr/bin/env bash
# Remove generated DOCX/PPTX files older than RETAIN_DAYS (default 30).
# Cron entry suggestion:
#   30 3 * * *  cd /opt/yozuvchim && ./scripts/cleanup-old-files.sh >> /var/log/yozuvchim-cleanup.log 2>&1

set -euo pipefail

cd "$(dirname "$0")/.."

RETAIN_DAYS="${FILES_RETAIN_DAYS:-30}"

echo "[$(date -u +%FT%TZ)] cleaning files older than $RETAIN_DAYS days from bot_data volume"

# bot/backend share the bot_data volume mounted at /app/data inside the bot container.
# It contains per-user subfolders with DOCX/PPTX outputs.
docker compose exec -T bot sh -lc "
  find /app/data -type f \\( -name '*.docx' -o -name '*.pptx' -o -name '*.pdf' \\) -mtime +$RETAIN_DAYS -print -delete
  # Drop empty directories left behind
  find /app/data -mindepth 1 -type d -empty -delete
"

echo "[$(date -u +%FT%TZ)] done."
