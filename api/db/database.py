from fastapi import HTTPException, status
from supabase import Client, create_client

from core.config import get_settings


def get_supabase_client() -> Client:
    """Create and return a Supabase client configured with the anon key.

    Use this for all normal request handling (auth, products, cart, orders).
    """
    settings = get_settings()
    return create_client(str(settings.supabase_url).rstrip("/"), settings.supabase_key)


def get_supabase_admin_client() -> Client:
    """Create and return a Supabase client configured with the service role key.

    This client can manage users through the Auth Admin API (listing accounts,
    updating roles). It bypasses Row Level Security, so it must only be used
    inside admin-only endpoints and never exposed to request handlers that
    read arbitrary client input.
    """
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_SERVICE_ROLE_KEY is not configured.",
        )
    return create_client(
        str(settings.supabase_url).rstrip("/"), settings.supabase_service_role_key
    )