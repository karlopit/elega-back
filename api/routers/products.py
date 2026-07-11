import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.security import require_authenticated_user, require_admin_user
from db.database import get_supabase_client
from models.schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ProductResponse])
@limiter.limit("30/minute")
async def list_products(request: Request, include_inactive: bool = False) -> list[ProductResponse]:
    """Return products available in the catalog (optionally including inactive ones)."""
    supabase = get_supabase_client()
    query = supabase.table("products").select("*")
    
    if not include_inactive:
        query = query.eq("is_active", True)
        
    response = query.order("created_at", desc=True).execute()
    return response.data


@router.get("/{product_id}", response_model=ProductResponse)
@limiter.limit("30/minute")
async def get_product(request: Request, product_id: UUID, include_inactive: bool = False) -> ProductResponse:
    """Return one product by its identifier (optionally including inactive ones)."""
    supabase = get_supabase_client()
    query = supabase.table("products").select("*").eq("id", str(product_id))
    
    if not include_inactive:
        query = query.eq("is_active", True)
        
    response = query.limit(1).execute()

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return response.data[0]


from uuid import uuid4

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_product(
    request: Request,
    payload: ProductCreate,
    admin_user_id: str = Depends(require_admin_user),
) -> ProductResponse:
    """Create a product from validated product fields and return it."""
    supabase = get_supabase_client()
    response = (
        supabase.table("products")
        .insert(payload.model_dump(mode="json"))
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create product.",
        )

    return response.data[0]


@router.patch("/{product_id}", response_model=ProductResponse)
@limiter.limit("10/minute")
async def update_product(
    request: Request,
    product_id: UUID,
    payload: ProductUpdate,
    admin_user_id: str = Depends(require_admin_user),
) -> ProductResponse:
    """Update a product by its identifier and return the updated product."""
    updates = payload.model_dump(mode="json", exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No product fields were provided.",
        )

    supabase = get_supabase_client()
    response = (
        supabase.table("products")
        .update(updates)
        .eq("id", str(product_id))
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )

    return response.data[0]


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_product(
    request: Request,
    product_id: UUID,
    admin_user_id: str = Depends(require_admin_user),
) -> None:
    """Delete a product by its identifier."""
    supabase = get_supabase_client()
    response = (
        supabase.table("products")
        .delete()
        .eq("id", str(product_id))
        .execute()
    )
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or could not be deleted.",
        )


@router.post("/upload-image", response_model=dict)
@limiter.limit("5/minute")
async def upload_product_image(
    request: Request,
    file: UploadFile = File(...),
    admin_user_id: str = Depends(require_admin_user),
) -> dict:
    """Upload an image to Supabase Storage and return its public URL."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed.",
        )
    
    # 5MB size limit
    MAX_SIZE = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 5MB limit.",
        )
        
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid4()}.{ext}"
    
    supabase = get_supabase_client()
    try:
        # Upload to Supabase bucket 'product-images'
        supabase.storage.from_("product-images").upload(
            path=filename,
            file=content,
            file_options={"content-type": file.content_type}
        )
        
        public_url = supabase.storage.from_("product-images").get_public_url(filename)
        return {"image_url": public_url}
        
    except Exception as exc:
        logger.exception("Failed to upload image to Supabase Storage")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload image to storage. Please ensure 'product-images' bucket is created and public in Supabase.",
        ) from exc
