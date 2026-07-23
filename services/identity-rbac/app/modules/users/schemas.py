from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    default_role_id: int
    mfa_enabled: bool
    status: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    default_role_id: int
    # Password is optional at creation — an admin can provision an account
    # that the user activates via the forgot-password flow, avoiding the
    # anti-pattern of an admin ever knowing a user's real password.
    password: str | None = Field(default=None, min_length=12)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    default_role_id: int | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended|deactivated)$")
    mfa_enabled: bool | None = None


class UserFilter(BaseModel):
    status: str | None = None
    default_role_id: int | None = None
    email_ilike: str | None = None
