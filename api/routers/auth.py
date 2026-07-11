from fastapi import APIRouter, HTTPException, Request, status
from gotrue.errors import AuthApiError
from slowapi import Limiter
from slowapi.util import get_remote_address
import logging

from db.database import get_supabase_client
from models.schemas import AuthResponse, UserLoginRequest, UserRegisterRequest

from core.security import get_user_role
from core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


def _build_auth_response(auth_data: object) -> AuthResponse:
    session = getattr(auth_data, "session", None)
    user = getattr(auth_data, "user", None)

    if session is None or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    role = get_user_role(user)

    return AuthResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        refresh_token=session.refresh_token,
        user_id=user.id,
        email=user.email,
        role=role,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def register_user(request: Request, payload: UserRegisterRequest) -> AuthResponse:
    """Create a customer account and return its authentication session."""
    supabase = get_supabase_client()
    settings = get_settings()
    role = "admin" if payload.email in settings.admin_emails else "user"

    try:
        auth_data = supabase.auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {
                    "data": {
                        "full_name": payload.full_name,
                        "role": role
                    }
                },
            }
        )
    except AuthApiError as exc:
        logger.warning("Supabase sign_up failed: %s", repr(exc))
        err_msg = getattr(exc, "message", str(exc))
        if "rate limit" in err_msg.lower() or "rate limit" in repr(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many sign-up attempts. Please wait a few minutes and try again.",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg if err_msg else "Unable to register with the provided credentials.",
        ) from None

    # When Supabase has email confirmation enabled, sign_up returns a user
    # but no session. Handle this gracefully instead of returning a 401.
    user = getattr(auth_data, "user", None)
    session = getattr(auth_data, "session", None)

    if user and session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A confirmation email has been sent. Please verify your email before signing in.",
        )

    return _build_auth_response(auth_data)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login_user(request: Request, payload: UserLoginRequest) -> AuthResponse:
    """Authenticate a customer and return an access token session."""
    supabase = get_supabase_client()

    try:
        auth_data = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except AuthApiError as exc:
        err_msg = getattr(exc, "message", str(exc))
        detail = err_msg if err_msg else "Invalid email or password."
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from None

    return _build_auth_response(auth_data)
