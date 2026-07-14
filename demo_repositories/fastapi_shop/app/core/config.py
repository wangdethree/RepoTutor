from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FastAPI Shop"
    jwt_secret: str = "demo-secret"
    jwt_expire_minutes: int = 60
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()

