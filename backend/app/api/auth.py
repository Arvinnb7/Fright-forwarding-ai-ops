"""Authentication, self-serve signup, and organization membership."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_org_admin
from app.core.security import create_access_token, verify_password
from app.core.tenancy import bypass_tenant_isolation
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import (
    InviteUserRequest,
    OrganizationOut,
    SignupRequest,
    SignupResponse,
    Token,
    UserOut,
    UserUpdateRequest,
)
from app.services.org_service import SignupError, add_member, create_organization_with_admin

router = APIRouter()


@router.post("/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """Create a new organization and its first administrator."""
    try:
        org, user = create_organization_with_admin(
            db,
            company_name=payload.company_name,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except SignupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SignupResponse(
        organization=OrganizationOut.model_validate(org),
        user=UserOut.model_validate(user),
        access_token=create_access_token(user.id),
    )


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    # OAuth2PasswordRequestForm calls it `username`; we treat it as the email.
    # Cross-tenant by necessity: the organization is unknown until we find the user.
    with bypass_tenant_isolation(db):
        user = db.execute(
            select(User).where(func.lower(User.email) == form.username.lower())
        ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(
        form.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/organization", response_model=OrganizationOut)
def my_organization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    with bypass_tenant_isolation(db):
        org = db.get(Organization, current_user.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/users", response_model=list[UserOut])
def list_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """Members of the caller's organization (explicitly scoped: User is not a
    tenant-filtered model, since login must find users before a tenant exists)."""
    with bypass_tenant_isolation(db):
        return list(
            db.execute(
                select(User)
                .where(User.organization_id == current_user.organization_id)
                .order_by(User.id)
            ).scalars().all()
        )


@router.post("/users", response_model=UserOut, status_code=201)
def invite_member(
    payload: InviteUserRequest,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> User:
    try:
        return add_member(
            db,
            organization_id=current_user.organization_id,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            full_name=payload.full_name,
        )
    except SignupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/users/{user_id}", response_model=UserOut)
def update_member(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> User:
    with bypass_tenant_isolation(db):
        user = db.get(User, user_id)
        # Never allow touching a member of another organization.
        if user is None or user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id == current_user.id and payload.role is not None:
            raise HTTPException(
                status_code=400, detail="You cannot change your own role."
            )
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
    return user
