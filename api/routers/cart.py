from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from db.database import get_supabase_client
from models.schemas import CartItemRequest, CartItemResponse, CartResponse
from core.security import ensure_user_access, require_authenticated_user

router = APIRouter(prefix="/cart", tags=["cart"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{user_id}", response_model=CartResponse)
@limiter.limit("30/minute")
async def get_cart(
    request: Request,
    user_id: UUID,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> CartResponse:
    """Return all cart items for a customer."""
    ensure_user_access(str(user_id), authenticated_user_id)
    supabase = get_supabase_client()
    response = (
        supabase.table("cart_items")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return CartResponse(items=response.data)


@router.post("/{user_id}/items", response_model=CartItemResponse)
@limiter.limit("20/minute")
async def upsert_cart_item(
    request: Request,
    user_id: UUID,
    payload: CartItemRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> CartItemResponse:
    """Add a product to a cart or replace its existing quantity."""
    ensure_user_access(str(user_id), authenticated_user_id)
    supabase = get_supabase_client()
    response = (
        supabase.table("cart_items")
        .upsert(
            {
                "user_id": str(user_id),
                "product_id": str(payload.product_id),
                "quantity": payload.quantity,
            },
            on_conflict="user_id,product_id",
        )
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update cart item.",
        )

    return response.data[0]


@router.delete("/{user_id}/items/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def remove_cart_item(
    request: Request,
    user_id: UUID,
    product_id: UUID,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> None:
    """Remove a product from a customer's cart."""
    ensure_user_access(str(user_id), authenticated_user_id)
    supabase = get_supabase_client()
    supabase.table("cart_items").delete().eq("user_id", str(user_id)).eq(
        "product_id",
        str(product_id),
    ).execute()
