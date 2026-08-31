"""
Data retention router — GDPR right-to-export and right-to-delete.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import get_current_user
from app.services.audit import export_user_data, anonymize_user

router = APIRouter(prefix="/api", tags=["data-retention"])


@router.get("/users/{user_id}/data-export")
def get_user_data_export(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GDPR right-to-export: returns all data associated with the given user.
    Only the user themselves or an Administrator may call this.
    """
    if current_user.id != user_id and current_user.role != "Administrator":
        raise HTTPException(status_code=403, detail="Access denied.")

    data = export_user_data(db, user_id)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.delete("/users/{user_id}/data")
def delete_user_data(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GDPR right-to-delete: anonymises the user record and deactivates it.
    Only the user themselves or an Administrator may call this.
    """
    if current_user.id != user_id and current_user.role != "Administrator":
        raise HTTPException(status_code=403, detail="Access denied.")

    success = anonymize_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")

    db.commit()
    return {"message": "User data anonymised successfully."}
