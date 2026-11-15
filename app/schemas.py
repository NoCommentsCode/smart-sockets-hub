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
    password: str = Field(min_length=6, max_length=72)
    role: UserRole = UserRole.user


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    password: str | None = Field(default=None, min_length=6, max_length=72)
    role: UserRole | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    current_password: str
    username: str | None = Field(default=None, min_length=3, max_length=64)
    new_password: str | None = Field(default=None, min_length=6, max_length=72)


class RelayConfigItem(BaseModel):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=32)
    default_state: bool | None = None


class ControllerConfigUpdate(BaseModel):
    device_name: str | None = Field(default=None, min_length=1, max_length=32)
    relays: list[RelayConfigItem] | None = None


class RelayConfigOut(BaseModel):
    id: int
    name: str
    default_state: bool


class ControllerConfigOut(BaseModel):
    device_name: str
    relays: list[RelayConfigOut]


class RelayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    relay_id: int
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