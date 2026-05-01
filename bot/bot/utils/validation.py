from __future__ import annotations

import os
from typing import Iterable, Mapping, Sequence


def ensure_env_vars_exist(names: Iterable[str]) -> None:
    """
    Ensure that required environment variables exist and are non-empty.

    Args:
        names: iterable of ENV VAR NAMES (e.g. ["BOT_TOKEN", "DATABASE_URL"])

    Raises:
        RuntimeError: if any required variable is missing or empty
    """
    missing = []

    for name in names:
        if not name:
            continue
        value = os.getenv(name)
        if value is None or not value.strip():
            missing.append(name)

    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )


def ensure_values_present(values: Mapping[str, object]) -> None:
    """
    Ensure that provided values are present (non-empty).

    Args:
        values: mapping of logical name -> value
                e.g. {"BOT_TOKEN": settings.bot_token}

    Raises:
        RuntimeError: if any value is missing
    """
    missing = []

    for name, value in values.items():
        if value is None:
            missing.append(name)
            continue

        if isinstance(value, str) and not value.strip():
            missing.append(name)

    if missing:
        raise RuntimeError(
            "Missing required configuration values: " + ", ".join(missing)
        )
