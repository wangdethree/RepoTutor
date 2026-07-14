from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.schemas.user import UserRead


def create_access_token(user_id: int) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire_at}, settings.jwt_secret, algorithm="HS256")


def get_current_user() -> UserRead:
    # 演示项目不真正校验请求头，RepoTutor 只做静态分析，不会执行这里的代码。
    return UserRead(id=1, email="demo@example.com", is_active=True)

