from pydantic import BaseModel


class ProductRead(BaseModel):
    id: int
    name: str
    price: float
    stock: int

