from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User
from app.schemas import User as UserResponse
from app.auth import get_current_user, require_role

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db), current_user: User = Depends(require_role("Administrator"))):
    """Retrieve all registered users/reviewers."""
    return db.query(User).all()

@router.get("/me", response_model=UserResponse)
def get_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retrieve details of a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user
