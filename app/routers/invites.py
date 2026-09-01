"""
Invites router — company onboarding via tokenized team invites.

Admins (SuperAdmin / Administrator) create an invite for an email + role. The
invite carries a one-time token that can be sent to the invitee directly
(email delivery is a later phase). Endpoints:

- POST   /api/organizations/{org_id}/invites     create an invite (admin)
- GET    /api/organizations/{org_id}/invites     list pending invites (admin)
- POST   /api/invites/accept                     redeem a token into a user
"""

import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, Invite
from app.schemas import InviteCreate, InviteAccept, Invite as InviteResponse
from app.auth import get_password_hash, require_role

router = APIRouter(prefix="/api", tags=["invites"])

ADMIN_ROLES = (UserRole.SUPER_ADMIN.value, UserRole.ADMINISTRATOR.value)


@router.post("/organizations/{org_id}/invites", response_model=InviteResponse)
def create_invite(
    org_id: str,
    invite_in: InviteCreate,
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """Issue a pending invite for ``invite_in.email`` scoped to ``org_id``."""
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only invite users into your own organization.",
        )
    if not (invite_in.email and invite_in.email.strip()):
        raise HTTPException(status_code=422, detail="email is required.")

    existing_user = db.query(User).filter(User.email == invite_in.email.strip()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with that email already exists.")

    existing_invite = db.query(Invite).filter(
        Invite.email == invite_in.email.strip(),
        Invite.organization_id == org_id,
        Invite.status == "pending",
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="An invite for that email is already pending.")

    token = uuid.uuid4().hex
    invite = Invite(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        email=invite_in.email.strip(),
        role=invite_in.role or UserRole.REVIEWER.value,
        token=token,
        status="pending",
        invited_by=current_user.id,
        created_at=datetime.datetime.utcnow(),
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/organizations/{org_id}/invites", response_model=list[InviteResponse])
def list_invites(
    org_id: str,
    current_user: User = Depends(require_role(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    """List pending invites for ``org_id`` (admin only)."""
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view invites in your own organization.",
        )
    return db.query(Invite).filter(
        Invite.organization_id == org_id,
        Invite.status == "pending",
    ).all()


@router.post("/invites/accept")
def accept_invite(accept_in: InviteAccept, db: Session = Depends(get_db)):
    """Redeem a one-time invite token into a platform user."""
    invite = db.query(Invite).filter(Invite.token == accept_in.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite already used.")
    if invite.expires_at and invite.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite expired.")

    existing = db.query(User).filter(
        (User.username == accept_in.username) | (User.email == invite.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered.")

    user = User(
        id=str(uuid.uuid4()),
        username=accept_in.username,
        email=invite.email,
        hashed_password=get_password_hash(accept_in.password),
        role=invite.role,
        active=True,
        organization_id=invite.organization_id,
    )
    db.add(user)
    invite.status = "accepted"
    db.commit()
    return {"detail": "Invite accepted. You can now log in.", "email": invite.email}