from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas import LoginRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")

    token = create_access_token(user.id, user.role.value)
    response.set_cookie(
        "access_token", token,
        httponly=True, samesite="lax",          # защита от CSRF + XSS-кражи токена
        max_age=settings.access_token_expire_minutes * 60,
        # secure=True — включить при работе через HTTPS
    )
    return {"user": UserOut.model_validate(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user