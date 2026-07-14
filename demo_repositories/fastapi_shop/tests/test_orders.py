from app.services.order_service import OrderService


def test_create_order() -> None:
    assert OrderService().list_orders(user_id=1)[0].status == "created"

