from pydantic import BaseModel


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = 1


class OrderCreate(BaseModel):
    items: list[OrderItemCreate]


class OrderRead(BaseModel):
    id: int
    status: str

