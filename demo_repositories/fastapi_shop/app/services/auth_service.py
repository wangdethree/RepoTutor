from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse


class AuthService:
    def __init__(self) -> None:
        self.user_repository = UserRepository()

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.user_repository.get_by_email(email)
        if not user:
            raise ValueError("invalid credentials")
        return TokenResponse(access_token=create_access_token(user.id))

