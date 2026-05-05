#!/bin/sh
# Backend entrypoint: apply Prisma migrations safely, then start the API.
#
# Why this dance:
#   - Brand-new DB → just `migrate deploy` and we're done.
#   - DB previously created with `db push` (dev) → tables already exist, so
#     `migrate deploy` would fail with "P3005: schema is not empty".
#     We detect that case and mark the initial migration as applied via
#     `migrate resolve`, then continue.

set -e

cd /app

# Wait briefly for the DB to accept connections. We use `prisma db execute`
# with a noop SELECT — it succeeds whenever the connection is up, regardless
# of the migration state.
echo "[entrypoint] waiting for database…"
for i in $(seq 1 30); do
  if echo "SELECT 1;" | npx prisma db execute --stdin --schema prisma/schema.prisma >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Run migrate deploy. If the DB has tables but no _prisma_migrations table
# (because it was originally provisioned with `prisma db push`), Prisma
# returns P3005. In that case, mark every existing migration as applied
# (baseline) and retry.
echo "[entrypoint] applying migrations"
deploy_out=$(npx prisma migrate deploy --schema prisma/schema.prisma 2>&1) || deploy_failed=1
echo "$deploy_out"

case "$deploy_out" in
  *"P3005"*|*"database schema is not empty"*)
    echo "[entrypoint] DB has existing schema — baselining migrations"
    for m in $(ls prisma/migrations 2>/dev/null | grep -v migration_lock.toml | sort); do
      [ -d "prisma/migrations/$m" ] || continue
      echo "[entrypoint]   marking $m as applied"
      npx prisma migrate resolve --applied "$m" --schema prisma/schema.prisma || true
    done
    echo "[entrypoint] retrying migrate deploy"
    npx prisma migrate deploy --schema prisma/schema.prisma
    ;;
  *)
    if [ "${deploy_failed:-0}" = "1" ]; then
      echo "[entrypoint] migrate deploy failed" >&2
      exit 1
    fi
    ;;
esac

echo "[entrypoint] starting API"
exec node dist/main.js
