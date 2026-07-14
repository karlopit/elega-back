import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from gotrue.errors import AuthApiError
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.security import get_user_role, require_admin_user
from db.database import get_supabase_admin_client
from models.schemas import UserResponse, UserRoleUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


def _to_user_response(user) -> UserResponse:
    """Map a Supabase auth user object to the API's UserResponse shape."""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=(user.user_metadata or {}).get("full_name"),
        role=get_user_role(user),
        created_at=user.created_at,
    )


@router.get("", response_model=list[UserResponse])
@limiter.limit("20/minute")
async def list_users(
    request: Request,
    admin_user_id: str = Depends(require_admin_user),
) -> list[UserResponse]:
    """Return every registered account with its role, for admin management."""
    supabase_admin = get_supabase_admin_client()

    try:
        response = supabase_admin.auth.admin.list_users()
    except AuthApiError as exc:
        logger.exception("Failed to list users from Supabase Auth")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load users.",
        ) from exc

    users = response if isinstance(response, list) else getattr(response, "users", [])
    return [_to_user_response(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
@limiter.limit("20/minute")
async def update_user_role(
    request: Request,
    user_id: str,
    payload: UserRoleUpdateRequest,
    admin_user_id: str = Depends(require_admin_user),
) -> UserResponse:
    """Update a user's role. Admins cannot change their own role."""
    if user_id == admin_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )

    supabase_admin = get_supabase_admin_client()

    try:
        response = supabase_admin.auth.admin.update_user_by_id(
            user_id,
            {"user_metadata": {"role": payload.role.value}},
        )
    except AuthApiError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from None

    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update user role.",
        )

    return _to_user_response(user)