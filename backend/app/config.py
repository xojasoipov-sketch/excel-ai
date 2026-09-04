"""Runtime settings lookup: environment variable first, then the `app_config`
table in Supabase.

Environment variables stay the primary source — nothing about deployment
changes. The database layer exists so keys that need rotating (the AI provider
keys especially) can be changed without a redeploy, and so config can be added
when the hosting provider's env-var API isn't reachable.

Values are cached after the first read; call `refresh()` to pick up a change
without restarting the process.
"""
import os
from typing import Dict, Optional

_cache: Optional[Dict[str, str]] = None


def _load_from_db() -> Dict[str, str]:
    try:
        from .db import get_db
        rows = get_db().table("app_config").select("key,value").execute().data or []
        return {row["key"]: row["value"] for row in rows}
    except Exception as e:
        # Config in the DB is a convenience, never a hard dependency: a missing
        # table or an unreachable database must not stop the app from booting.
        print(f"app_config could not be read ({e}); using environment variables only.")
        return {}


def refresh() -> None:
    global _cache
    _cache = None


def get(name: str, default: Optional[str] = None) -> Optional[str]:
    env_value = os.getenv(name)
    if env_value:
        return env_value

    global _cache
    if _cache is None:
        _cache = _load_from_db()
    return _cache.get(name) or default
