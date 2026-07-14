from app.schemas.order import OrderRead


class OrderRepository:
    def create_order(self, user_id: int) -> OrderRead:
        return OrderRead(id=1001, status="created")

    def list_orders(self, user_id: int) -> list[OrderRead]:
        return [OrderRead(id=1001, status="created")]

