from sqlalchemy import Column, Float, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    order_items = relationship("OrderItem", back_populates="product")

