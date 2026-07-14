from app.schemas.user import UserRead


class UserRepository:
    def get_by_email(self, email: str) -> UserRead | None:
        return UserRead(id=1, email=email, is_active=True)

