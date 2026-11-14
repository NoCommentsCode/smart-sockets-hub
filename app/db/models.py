import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Controller(Base):
    """ESP32-контроллер. Одна плата управляет N розетками."""
    __tablename__ = "controllers"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    version: Mapped[str] = mapped_column(String(32), default="")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    relays: Mapped[list["Relay"]] = relationship(
        back_populates="controller", cascade="all, delete-orphan", lazy="selectin"
    )


class Relay(Base):
    """Розетка. relay_id — локальный ID на стороне ESP32."""
    __tablename__ = "relays"
    __table_args__ = (UniqueConstraint("controller_id", "relay_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    controller_id: Mapped[int] = mapped_column(ForeignKey("controllers.id"))
    relay_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    controller: Mapped[Controller] = relationship(back_populates="relays")