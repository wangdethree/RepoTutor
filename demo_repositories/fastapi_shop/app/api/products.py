from fastapi import APIRouter

from app.schemas.product import ProductRead
from app.services.product_service import ProductService


router = APIRouter()


@router.get("/", response_model=list[ProductRead])
def list_products() -> list[ProductRead]:
    return ProductService().list_products()


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int) -> ProductRead:
    return ProductService().get_product(product_id)

