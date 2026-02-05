"""
Supabase Client - Database Connection Management
Compatible with supabase-py v2.x
"""

from functools import lru_cache
from supabase import create_client, Client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """
    Get Supabase client with anon key (respects RLS).
    Use for user-facing operations.
    """
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key.get_secret_value()
    )


@lru_cache
def get_supabase_admin_client() -> Client:
    """
    Get Supabase client with service role key (bypasses RLS).
    Use ONLY for admin/system operations.
    """
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value()
    )


# Convenience aliases
supabase = get_supabase_client
supabase_admin = get_supabase_admin_client
