"""Thin Supabase client wrapper. Uses the service-role key (server-side only,
never sent to the frontend) so the backend can read/write every table regardless
of Row Level Security — RLS exists purely as a safety net against direct client
access, not as the backend's own access control (that's handled in app/auth.py).
"""
import os
from functools import lru_cache

from supabase import create_client, Client


@lru_cache
def get_db() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY is not configured. "
            "Add them to backend/.env (see backend/.env.example)."
        )
    return create_client(url, key)
