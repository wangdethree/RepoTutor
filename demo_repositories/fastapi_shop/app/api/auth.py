from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.user import LoginRequest, TokenResponse, UserRead
from app.services.auth_service import AuthService


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    service = AuthService()
    return service.login(payload.email, payload.password)


@router.get("/me", response_model=UserRead)
def me(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    return current_user

