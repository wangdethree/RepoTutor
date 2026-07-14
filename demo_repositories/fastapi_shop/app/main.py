from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.orders import router as order_router
from app.api.products import router as product_router
from app.core.config import settings


app = FastAPI(title=settings.app_name)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(product_router, prefix="/api/products", tags=["products"])
app.include_router(order_router, prefix="/api/orders", tags=["orders"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

