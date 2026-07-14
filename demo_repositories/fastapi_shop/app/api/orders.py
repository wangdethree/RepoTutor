from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.order import OrderCreate, OrderRead
from app.schemas.user import UserRead
from app.services.order_service import OrderService


router = APIRouter()


@router.post("/", response_model=OrderRead)
def create_order(payload: OrderCreate, current_user: UserRead = Depends(get_current_user)) -> OrderRead:
    return OrderService().create_order(current_user.id, payload)


@router.get("/", response_model=list[OrderRead])
def list_orders(current_user: UserRead = Depends(get_current_user)) -> list[OrderRead]:
    return OrderService().list_orders(current_user.id)

