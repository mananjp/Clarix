"""
Unit tests for Enterprise SSO Service (Phase 5).
"""

import os
import sys
import base64

from app.models import User
from app.services.enterprise_sso import EnterpriseSSOService

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestEnterpriseSSOService:
    def test_save_and_get_sso_config(self, db_session, seeded_db):
        config = EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer="https://sts.windows.net/enterprise-tenant-id/",
            idp_sso_url="https://login.microsoftonline.com/enterprise-tenant-id/saml2",
            protocol="SAML2",
            enabled=True,
            auto_provision=True,
            default_role="ComplianceOfficer",
        )
        assert config.organization_id == "test_org"
        assert config.enabled is True

        retrieved = EnterpriseSSOService.get_config(db_session, "test_org")
        assert retrieved is not None
        assert retrieved.idp_issuer == "https://sts.windows.net/enterprise-tenant-id/"

    def test_parse_saml_assertion(self):
        sample_xml = """<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
            <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
                <saml:Subject>
                    <saml:NameID>sarah.compliance@enterprise.com</saml:NameID>
                </saml:Subject>
                <saml:AttributeStatement>
                    <saml:Attribute Name="username">
                        <saml:AttributeValue>sarah_c</saml:AttributeValue>
                    </saml:Attribute>
                    <saml:Attribute Name="role">
                        <saml:AttributeValue>ComplianceOfficer</saml:AttributeValue>
                    </saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>"""

        b64_xml = base64.b64encode(sample_xml.encode("utf-8")).decode("utf-8")
        parsed = EnterpriseSSOService.parse_saml_assertion(b64_xml)
        assert parsed["email"] == "sarah.compliance@enterprise.com"
        assert parsed["username"] == "sarah_c"
        assert parsed["role"] == "ComplianceOfficer"

    def test_authenticate_or_provision_user(self, db_session, seeded_db):
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer="https://idp.okta.com/app/clarix",
            idp_sso_url="https://idp.okta.com/app/clarix/sso/saml",
            enabled=True,
            auto_provision=True,
            default_role="Reviewer",
        )

        user, token = EnterpriseSSOService.authenticate_or_provision_user(
            db_session,
            org_id="test_org",
            email="new_sso_user@enterprise.com",
            username="new_sso_user",
        )
        assert user.email == "new_sso_user@enterprise.com"
        assert user.organization_id == "test_org"
        assert isinstance(token, str)
        assert len(token) > 20

        # Verify persisted in database
        db_user = db_session.query(User).filter(User.email == "new_sso_user@enterprise.com").first()
        assert db_user is not None
