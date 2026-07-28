"""Auth, signup and organization schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    company_name: str | None = None
    default_currency: str | None = None
    default_markup_percent: float | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    role: UserRole
    organization_id: int


class SignupRequest(BaseModel):
    """Self-serve onboarding: creates an organization and its first admin."""

    company_name: str = Field(min_length=2, max_length=255)
    full_name: str | None = None
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class SignupResponse(BaseModel):
    organization: OrganizationOut
    user: UserOut
    access_token: str
    token_type: str = "bearer"


class InviteUserRequest(BaseModel):
    """An admin adds a colleague to their own organization."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    role: UserRole = UserRole.COORDINATOR


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
