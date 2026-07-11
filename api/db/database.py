from supabase import Client, create_client

from core.config import get_settings


def get_supabase_client() -> Client:
    """Create and return a Supabase client configured from environment variables."""
    settings = get_settings()
    return create_client(str(settings.supabase_url).rstrip("/"), settings.supabase_key)
