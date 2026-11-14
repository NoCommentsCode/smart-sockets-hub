from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import get_db
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


async def _guard_last_admin(db: AsyncSession, user: User, will_stay_admin: bool) -> None:
    if will_stay_admin or user.role != UserRole.admin or not user.is_active:
        return
    others = (await db.execute(
        select(func.count()).select_from(User).where(
            User.role == UserRole.admin, User.is_active == True, User.id != user.id
        )
    )).scalar()
    if others == 0:
        raise HTTPException(400, "Нельзя убрать последнего администратора")


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).order_by(User.id))).scalars().all()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.username == data.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(400, "Такой логин уже занят")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: int, data: UserUpdate,
                      admin: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    if data.username is not None and data.username != user.username:
        exists = (await db.execute(
            select(User).where(User.username == data.username, User.id != user.id)
        )).scalar_one_or_none()
        if exists:
            raise HTTPException(400, "Такой логин уже занят")
        user.username = data.username

    new_role = data.role if data.role is not None else user.role
    new_active = data.is_active if data.is_active is not None else user.is_active
    await _guard_last_admin(db, user, new_role == UserRole.admin and new_active)

    if data.password is not None:
        user.password_hash = hash_password(data.password)
    user.role = new_role
    user.is_active = new_active
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, admin: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(400, "Нельзя удалить самого себя")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    await _guard_last_admin(db, user, will_stay_admin=False)
    await db.delete(user)
    await db.commit()