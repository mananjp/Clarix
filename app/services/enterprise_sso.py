"""
Enterprise Single Sign-On (SSO) & Identity Federation Service.

Supports SAML 2.0 and OIDC identity providers (Okta, Azure AD / Microsoft Entra, Google Workspace).
"""

import uuid
import base64
import datetime
import logging
from typing import Dict, Any, Tuple, Optional
from xml.etree import ElementTree as ET
from sqlalchemy.orm import Session

from app.models import User, EnterpriseSSOConfig, UserRole
from app.auth import create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)


class EnterpriseSSOService:
    @classmethod
    def get_config(cls, db: Session, org_id: str) -> Optional[EnterpriseSSOConfig]:
        """Retrieve SSO configuration for an organization."""
        return db.query(EnterpriseSSOConfig).filter(EnterpriseSSOConfig.organization_id == org_id).first()

    @classmethod
    def save_config(
        cls,
        db: Session,
        *,
        org_id: str,
        idp_issuer: str,
        idp_sso_url: str,
        idp_certificate: Optional[str] = None,
        protocol: str = "SAML2",
        enabled: bool = True,
        auto_provision: bool = True,
        default_role: str = "Reviewer",
    ) -> EnterpriseSSOConfig:
        """Create or update enterprise SSO configuration for an organization."""
        config = cls.get_config(db, org_id)
        if not config:
            config = EnterpriseSSOConfig(
                id=f"sso_{uuid.uuid4().hex[:12]}",
                organization_id=org_id,
                idp_issuer=idp_issuer,
                idp_sso_url=idp_sso_url,
                idp_certificate=idp_certificate,
                protocol=protocol,
                enabled=enabled,
                auto_provision_users=auto_provision,
                default_role=default_role,
            )
            db.add(config)
        else:
            config.idp_issuer = idp_issuer
            config.idp_sso_url = idp_sso_url
            if idp_certificate:
                config.idp_certificate = idp_certificate
            config.protocol = protocol
            config.enabled = enabled
            config.auto_provision_users = auto_provision
            config.default_role = default_role

        db.commit()
        db.refresh(config)
        logger.info("Updated SSO config for organization %s (enabled: %s)", org_id, enabled)
        return config

    @classmethod
    def parse_saml_assertion(cls, saml_response_b64: str) -> Dict[str, Any]:
        """
        Parses a Base64-encoded SAML 2.0 XML assertion to extract user attributes.
        """
        try:
            xml_bytes = base64.b64decode(saml_response_b64)
            root = ET.fromstring(xml_bytes)

            # Namespace-agnostic element search

            # Extract NameID / Email
            email = None
            for elem in root.iter():
                if "NameID" in elem.tag:
                    email = elem.text.strip() if elem.text else None
                    break

            # Fallback attribute search
            attributes = {}
            for attr in root.iter():
                if "Attribute" in attr.tag:
                    attr_name = attr.attrib.get("Name") or attr.attrib.get("FriendlyName")
                    val_elem = attr.find(".//{*}AttributeValue")
                    if attr_name and val_elem is not None and val_elem.text:
                        attributes[attr_name.lower()] = val_elem.text.strip()

            user_email = email or attributes.get("email") or attributes.get("mail") or attributes.get("userprincipalname")
            username = attributes.get("username") or attributes.get("displayname") or (user_email.split("@")[0] if user_email else None)
            role = attributes.get("role") or attributes.get("groups")

            if not user_email:
                raise ValueError("Could not extract email address from SAML assertion.")

            return {
                "email": user_email,
                "username": username or user_email.split("@")[0],
                "role": role,
            }
        except Exception as e:
            logger.error("Failed to parse SAML response: %s", e)
            raise ValueError(f"SAML Assertion Parsing Error: {e}")

    @classmethod
    def authenticate_or_provision_user(
        cls,
        db: Session,
        org_id: str,
        email: str,
        username: str,
        role: Optional[str] = None,
    ) -> Tuple[User, str]:
        """
        Authenticates an existing SSO user or auto-provisions a new user in the organization,
        returning (user_object, jwt_access_token).
        """
        config = cls.get_config(db, org_id)
        if not config or not config.enabled:
            raise ValueError(f"SSO is not enabled for organization {org_id}.")

        user = db.query(User).filter(User.email == email).first()

        if not user:
            if not config.auto_provision_users:
                raise ValueError("User does not exist and auto-provisioning is disabled.")

            # Assign role
            assigned_role = role if role in [r.value for r in UserRole] else config.default_role

            user = User(
                id=str(uuid.uuid4()),
                organization_id=org_id,
                username=username,
                email=email,
                hashed_password=get_password_hash(uuid.uuid4().hex),  # Random password for SSO user
                role=assigned_role,
                active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Auto-provisioned SSO user %s in organization %s", user.email, org_id)

        # Issue JWT
        expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": user.username}, expires_delta=expires)
        return user, access_token
