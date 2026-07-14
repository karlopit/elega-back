from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from gotrue.errors import AuthApiError

from db.database import get_supabase_client
from core.config import get_settings
from models.schemas import UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_role(user) -> str:
    """Determine a user's role based on email configuration and metadata.

    The admin_emails allowlist always wins (bootstrap admins). Otherwise the
    role stored in user_metadata is used, set either at registration or later
    by an admin through PATCH /users/{user_id}/role.
    """
    settings = get_settings()
    if user.email in settings.admin_emails:
        return UserRole.admin.value

    metadata_role = user.user_metadata.get("role") if user.user_metadata else None
    if metadata_role in (UserRole.admin.value, UserRole.staff.value):
        return metadata_role

    return UserRole.user.value


def _get_authenticated_user(credentials: HTTPAuthorizationCredentials | None):
    """Validate a bearer token with Supabase Auth and return the auth user object."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )

    supabase = get_supabase_client()

    try:
        user_response = supabase.auth.get_user(credentials.credentials)
    except AuthApiError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from None

    user = getattr(user_response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )

    return user


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate a bearer token and return the authenticated user's id."""
    user = _get_authenticated_user(credentials)
    return user.id


def require_staff_or_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate a bearer token and ensure the caller has staff or admin privileges."""
    user = _get_authenticated_user(credentials)
    role = get_user_role(user)

    if role not in (UserRole.admin.value, UserRole.staff.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff or admin privileges required.",
        )

    return user.id


def require_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate a bearer token and ensure the caller has admin privileges."""
    user = _get_authenticated_user(credentials)
    role = get_user_role(user)

    if role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )

    return user.id


def ensure_user_access(requested_user_id: str, authenticated_user_id: str) -> None:
    """Ensure an authenticated user can only access their own customer data."""
    if requested_user_id != authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )