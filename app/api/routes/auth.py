from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas import LoginRequest, ProfileUpdate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Неверный логин или пароль")

    token = create_access_token(user.id, user.role.value)
    response.set_cookie(
        "access_token", token,
        httponly=True, samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return {"user": UserOut.model_validate(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(data: ProfileUpdate,
                    user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Текущий пароль указан неверно")
    if data.username is None and data.new_password is None:
        raise HTTPException(400, "Укажите новый логин или новый пароль")

    if data.username is not None and data.username != user.username:
        exists = (await db.execute(
            select(User).where(User.username == data.username, User.id != user.id)
        )).scalar_one_or_none()
        if exists:
            raise HTTPException(400, "Такой логин уже занят")
        user.username = data.username

    if data.new_password is not None:
        user.password_hash = hash_password(data.new_password)

    await db.commit()
    await db.refresh(user)
    return user