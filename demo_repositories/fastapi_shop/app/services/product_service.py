from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductRead


class ProductService:
    def __init__(self) -> None:
        self.product_repository = ProductRepository()

    def list_products(self) -> list[ProductRead]:
        return self.product_repository.list_products()

    def get_product(self, product_id: int) -> ProductRead:
        return self.product_repository.get_product(product_id)

