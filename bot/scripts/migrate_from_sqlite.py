"""
One-off migration: old SQLite DB → new PostgreSQL DB.

Run inside the bot container:
  docker compose ... cp academic_bot_backup.db bot:/tmp/old.db
  docker compose ... exec bot python3 /app/scripts/migrate_from_sqlite.py /tmp/old.db

Idempotent (uses ON CONFLICT DO NOTHING). Skips app_settings to avoid
overwriting freshly-seeded admin credentials.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any

import asyncpg


def _parse_datetime(value: Any) -> Any:
    """SQLite stores datetimes as ISO strings — convert to Python datetime."""
    if value is None or isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Try common formats with optional microseconds and timezone
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        # Last resort — fromisoformat is permissive about Z and timezone offsets
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# Tables and target columns. Source-only columns are auto-filtered.
# bool_columns are coerced 0/1 → False/True. json_columns are decoded.
TABLES: dict[str, dict[str, Any]] = {
    "users": {
        "pk": "id",
        "columns": [
            "id", "username", "full_name", "balance", "has_used_free_trial",
            "daily_limit", "referral_count", "is_blocked", "role", "language_code",
            "total_spent", "referred_by_id", "referral_tier", "plan",
            "total_documents", "total_orders", "time_saved", "last_active",
            "academic_context", "vip_expires_at", "created_at", "updated_at",
        ],
        "bool_columns": {"has_used_free_trial", "is_blocked"},
        "json_columns": {"academic_context"},
        "datetime_columns": {"last_active", "vip_expires_at", "created_at", "updated_at"},
        "has_serial": False,
    },
    "requests": {
        "pk": "id",
        "columns": [
            "id", "user_id", "doc_type", "title", "title_topic", "language",
            "level", "length", "price", "requirements_text", "custom_structure",
            "export_format", "citation_style", "quality_score", "meta_json",
            "is_free", "is_deleted", "result_text", "status",
            "current_step", "total_steps", "error_log", "result_path",
            "result_file_id", "download_token", "expires_at",
            "locked_by", "locked_at", "attempts", "created_at", "updated_at",
            "rating", "feedback",
        ],
        "bool_columns": {"is_free", "is_deleted"},
        "json_columns": {"meta_json"},
        "datetime_columns": {"expires_at", "locked_at", "created_at", "updated_at"},
        "has_serial": True,
    },
    "payments": {
        "pk": "id",
        "columns": [
            "id", "user_id", "invoice_id", "amount", "status",
            "screenshot_file_id", "created_at",
        ],
        "bool_columns": set(),
        "json_columns": set(),
        "datetime_columns": {"created_at"},
        "has_serial": True,
    },
    "tickets": {
        "pk": "id",
        "columns": [
            "id", "user_id", "ticket_id", "subject", "message", "status",
            "created_at",
        ],
        "bool_columns": set(),
        "json_columns": set(),
        "datetime_columns": {"created_at"},
        "has_serial": True,
    },
}


def _coerce(value: Any, *, is_bool: bool, is_json: bool, is_datetime: bool) -> Any:
    if value is None:
        return None
    if is_datetime:
        return _parse_datetime(value)
    if is_bool:
        return bool(value)
    if is_json:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            try:
                json.loads(value)  # validate
                return value
            except Exception:
                return "{}"
        return "{}"
    return value


async def migrate_table(
    src: sqlite3.Connection,
    dst: asyncpg.Connection,
    name: str,
    meta: dict[str, Any],
) -> None:
    src_cols = {row[1] for row in src.execute(f"PRAGMA table_info({name})").fetchall()}
    common = [c for c in meta["columns"] if c in src_cols]
    if not common:
        print(f"⚠️  {name}: no matching columns")
        return

    rows = src.execute(f"SELECT {','.join(common)} FROM {name}").fetchall()
    print(f"--- {name}: {len(rows)} rows from SQLite")

    placeholders = ",".join(f"${i + 1}" for i in range(len(common)))
    cols_sql = ",".join(f'"{c}"' for c in common)
    sql = (
        f"INSERT INTO {name} ({cols_sql}) VALUES ({placeholders}) "
        f"ON CONFLICT ({meta['pk']}) DO NOTHING"
    )

    inserted = skipped = errors = 0
    for row in rows:
        values = [
            _coerce(
                row[c],
                is_bool=c in meta["bool_columns"],
                is_json=c in meta["json_columns"],
                is_datetime=c in meta["datetime_columns"],
            )
            for c in common
        ]
        try:
            result = await dst.execute(sql, *values)
            if result.endswith(" 0"):
                skipped += 1
            else:
                inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"   error on row {row[meta['pk']]}: {e}")

    print(f"   ✓ inserted={inserted}  skipped(existing)={skipped}  errors={errors}")

    # Fix the auto-increment sequence so new inserts don't clash
    if meta["has_serial"]:
        max_id = await dst.fetchval(f"SELECT COALESCE(MAX(id), 0) FROM {name}")
        if max_id:
            await dst.execute(f"SELECT setval('{name}_id_seq', $1)", max_id)
            print(f"   {name}_id_seq → {max_id}")


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_from_sqlite.py <path-to-sqlite>")
        sys.exit(1)

    sqlite_path = sys.argv[1]
    if not os.path.exists(sqlite_path):
        print(f"SQLite file not found: {sqlite_path}")
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "")
    # asyncpg expects the plain postgresql:// URL (no SQLAlchemy +asyncpg)
    if "+asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg", "postgresql")

    if not db_url.startswith("postgres"):
        print("DATABASE_URL must be a postgres URL")
        sys.exit(1)

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row

    dst = await asyncpg.connect(db_url)

    # Register JSON codec so dict/json strings round-trip cleanly
    await dst.set_type_codec(
        "jsonb",
        encoder=lambda x: x if isinstance(x, str) else json.dumps(x, ensure_ascii=False),
        decoder=json.loads,
        schema="pg_catalog",
    )

    try:
        for name, meta in TABLES.items():
            await migrate_table(src, dst, name, meta)
    finally:
        src.close()
        await dst.close()

    print("\n✓ migration complete")


if __name__ == "__main__":
    asyncio.run(main())
