from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderCreate, OrderRead


class OrderService:
    def __init__(self) -> None:
        self.order_repository = OrderRepository()

    def create_order(self, user_id: int, payload: OrderCreate) -> OrderRead:
        return self.order_repository.create_order(user_id)

    def list_orders(self, user_id: int) -> list[OrderRead]:
        return self.order_repository.list_orders(user_id)

