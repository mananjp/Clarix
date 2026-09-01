"""
Enterprise SSO Router — SAML 2.0 / OIDC identity provider integration.
"""

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import require_role
from app.services.enterprise_sso import EnterpriseSSOService

router = APIRouter(prefix="/api/auth/sso", tags=["enterprise-sso"])


class SSOConfigPayload(BaseModel):
    organization_id: str = Field(..., description="Organization ID to configure SSO for")
    idp_issuer: str = Field(..., description="IDP Entity ID / Issuer URI")
    idp_sso_url: str = Field(..., description="IDP Single Sign-On URL")
    idp_certificate: Optional[str] = Field(None, description="X.509 public signing certificate")
    protocol: str = Field("SAML2", description="SSO Protocol (SAML2 or OIDC)")
    enabled: bool = Field(True, description="Enable or disable SSO")
    auto_provision_users: bool = Field(True, description="Automatically provision new users")
    default_role: str = Field("Reviewer", description="Default role for auto-provisioned users")


@router.post("/config")
def save_sso_configuration(
    payload: SSOConfigPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
):
    """
    Configure or update Enterprise SAML 2.0 / OIDC Identity Provider integration.
    Restricted to Administrators.
    """
    config = EnterpriseSSOService.save_config(
        db,
        org_id=payload.organization_id,
        idp_issuer=payload.idp_issuer,
        idp_sso_url=payload.idp_sso_url,
        idp_certificate=payload.idp_certificate,
        protocol=payload.protocol,
        enabled=payload.enabled,
        auto_provision=payload.auto_provision_users,
        default_role=payload.default_role,
    )
    return {
        "message": "Enterprise SSO configuration saved successfully.",
        "organization_id": config.organization_id,
        "protocol": config.protocol,
        "enabled": config.enabled,
        "auto_provision_users": config.auto_provision_users,
        "default_role": config.default_role,
    }


@router.get("/config/{org_id}")
def get_sso_configuration(
    org_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve SSO configuration and IDP login redirect URL for an organization.
    """
    config = EnterpriseSSOService.get_config(db, org_id)
    if not config:
        raise HTTPException(status_code=404, detail="SSO configuration not found for this organization.")

    return {
        "organization_id": config.organization_id,
        "protocol": config.protocol,
        "enabled": config.enabled,
        "idp_sso_url": config.idp_sso_url,
        "idp_issuer": config.idp_issuer,
        "secure": bool(config.idp_certificate),
    }


@router.post("/saml/callback")
def saml_callback(
    SAMLResponse: str = Form(..., description="Base64-encoded SAML 2.0 Response XML"),
    RelayState: Optional[str] = Form(None, description="Organization ID or target redirect"),
    db: Session = Depends(get_db),
):
    """
    Process SAML 2.0 Response assertion from Identity Provider (Okta, Azure AD / Entra ID, PingIdentity)
    and return an authenticated session JWT token.

    The assertion MUST carry a valid XML Signature that verifies against the
    organization's configured IdP signing certificate. Unsigned or tampered
    assertions are rejected outright.
    """
    org_id = RelayState or "default_org"

    try:
        attributes = EnterpriseSSOService.verify_and_parse_saml_assertion(
            db, org_id=org_id, saml_response_b64=SAMLResponse
        )
        user, access_token = EnterpriseSSOService.authenticate_or_provision_user(
            db,
            org_id=org_id,
            email=attributes["email"],
            username=attributes["username"],
            role=attributes.get("role"),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "organization_id": user.organization_id,
            },
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
