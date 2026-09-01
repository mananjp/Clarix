"""
Auth router — registration and login.
"""

import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Organization, UserRole
from app.schemas import UserCreate, User as UserResponse, Token
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.limiter import limiter

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register", response_model=UserResponse)
@limiter.limit("5/minute")
def register_user(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user.

    If ``organization_name`` is supplied, a new Organization is created and
    the registrant becomes that company's Super Admin (self-serve onboarding).
    Otherwise the user joins the shared ``default_org`` (used for the demo
    workspace and tests).
    """
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    if user_in.organization_name and user_in.organization_name.strip():
        org = Organization(
            id=str(uuid.uuid4()),
            name=user_in.organization_name.strip(),
            type="Asset Manager",
        )
        db.add(org)
        db.flush()
        organization_id = org.id
        role = UserRole.SUPER_ADMIN.value
    else:
        organization_id = "default_org"
        role = user_in.role or UserRole.REVIEWER.value

    db_user = User(
        id=str(uuid.uuid4()),
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=role,
        active=user_in.active,
        organization_id=organization_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/auth/token", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
