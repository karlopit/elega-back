from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from db.database import get_supabase_client
from models.schemas import OrderCreateRequest, OrderResponse, OrderStatus
from core.security import ensure_user_access, require_authenticated_user

router = APIRouter(prefix="/orders", tags=["orders"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/{user_id}", response_model=list[OrderResponse])
@limiter.limit("30/minute")
async def list_orders(
    request: Request,
    user_id: UUID,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> list[OrderResponse]:
    """Return a customer's orders ordered from newest to oldest."""
    ensure_user_access(str(user_id), authenticated_user_id)
    supabase = get_supabase_client()
    response = (
        supabase.table("orders")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_order(
    request: Request,
    payload: OrderCreateRequest,
    authenticated_user_id: str = Depends(require_authenticated_user),
) -> OrderResponse:
    """Create an order from validated order items and shipping details."""
    ensure_user_access(str(payload.user_id), authenticated_user_id)
    supabase = get_supabase_client()
    product_ids = [str(item.product_id) for item in payload.items]
    products_response = (
        supabase.table("products")
        .select("id,price,currency,stock_quantity,is_active")
        .in_("id", product_ids)
        .execute()
    )
    products = {product["id"]: product for product in products_response.data}

    if len(products) != len(product_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more products are unavailable.",
        )

    total_amount = Decimal("0.00")
    currency = None
    order_items = []

    for item in payload.items:
        product = products[str(item.product_id)]

        if not product["is_active"] or product["stock_quantity"] < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more products are unavailable.",
            )

        if currency is None:
            currency = product["currency"]
        elif currency != product["currency"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order items must use the same currency.",
            )

        unit_price = Decimal(str(product["price"]))
        total_amount += unit_price * item.quantity
        order_items.append(
            {
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "unit_price": str(unit_price),
            }
        )

    order_response = (
        supabase.table("orders")
        .insert(
            {
                "user_id": str(payload.user_id),
                "status": OrderStatus.pending.value,
                "total_amount": str(total_amount),
                "currency": currency,
                "shipping_address": payload.shipping_address,
            }
        )
        .execute()
    )

    if not order_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create order.",
        )

    order = order_response.data[0]
    order_item_rows = [
        {"order_id": order["id"], **order_item}
        for order_item in order_items
    ]
    supabase.table("order_items").insert(order_item_rows).execute()

    return order
