#!/usr/bin/env bash
# Generate strong random secrets for the production .env file.
# Usage:
#   ./scripts/generate-secrets.sh             # print to stdout
#   ./scripts/generate-secrets.sh -- > .env   # use as fresh .env (rare)

set -euo pipefail

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl not found. Install it first." >&2
  exit 1
fi

# 64-byte secrets, base64 encoded → ~88 chars, safe for env vars.
gen64() { openssl rand -base64 64 | tr -d '\n='; }
gen32() { openssl rand -base64 32 | tr -d '\n='; }
gen24() { openssl rand -base64 24 | tr -d '\n='; }

cat <<EOF
# === Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) ===
# Paste these into .env and KEEP THEM SECRET. Anyone with these can
# forge JWTs, read the DB, or sign in as admin.

JWT_SECRET=$(gen64)
JWT_REFRESH_SECRET=$(gen64)
POSTGRES_PASSWORD=$(gen32)

# Initial admin password (you'll change it via /admin/settings on first login).
ADMIN_LOGIN_PASSWORD=$(gen24)
EOF
