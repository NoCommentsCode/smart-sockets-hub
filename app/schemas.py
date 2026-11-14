from pydantic import BaseModel, ConfigDict, Field

from app.db.models import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: UserRole
    is_active: bool


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)  # bcrypt: максимум 72 байта
    role: UserRole = UserRole.user


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=72)
    role: UserRole | None = None
    is_active: bool | None = None


class RelayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int          # PK в нашей БД
    relay_id: int    # ID на стороне ESP32
    name: str
    state: bool


class ControllerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ip: str
    name: str
    version: str
    is_online: bool
    relays: list[RelayOut]


class StateRequest(BaseModel):
    state: bool