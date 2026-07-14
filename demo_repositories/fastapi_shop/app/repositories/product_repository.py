from app.schemas.product import ProductRead


class ProductRepository:
    def list_products(self) -> list[ProductRead]:
        return [ProductRead(id=1, name="Keyboard", price=299.0, stock=12)]

    def get_product(self, product_id: int) -> ProductRead:
        return ProductRead(id=product_id, name="Keyboard", price=299.0, stock=12)

