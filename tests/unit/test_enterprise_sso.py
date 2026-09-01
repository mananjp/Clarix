"""
Unit tests for Enterprise SSO Service — including SAML XML Signature
verification (the auth-bypass fix).
"""

import os
import sys
import base64
import datetime
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

import lxml.etree as ET
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from app.models import User
from app.services.enterprise_sso import EnterpriseSSOService
from app.services.saml_security import SamlVerificationError

DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMPLE_ISSUER = "https://idp.okta.com/app/clarix"


def _make_cert() -> tuple[RSAPrivateKey, str]:
    """Generate an RSA-SHA256 signing key and a self-signed X.509 cert (PEM)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "clarix-test-idp"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return key, pem


def _canonicalize(el: ET._Element) -> bytes:
    return ET.tostring(el, method="c14n", exclusive=True, with_comments=False)


def _hash_bytes(data: bytes, algo: str = "sha256") -> bytes:
    if algo == "sha1":
        digest = hashes.Hash(hashes.SHA1())
    else:
        digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()


def build_signed_saml_response(
    *,
    email: str = "sarah.compliance@enterprise.com",
    username: str = "sarah_c",
    role: str = "ComplianceOfficer",
    issuer: str = SAMPLE_ISSUER,
    key: RSAPrivateKey,
    not_before: str | None = None,
    not_on_or_after: str | None = None,
    tamper_after_signing: callable = None,
    omit_signature: bool = False,
) -> str:
    """
    Build a Base64 SAML 2.0 Response with a *real* XML Signature derived from
    `key`, so the verifier path is exercised end-to-end (not mocked).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    before = not_before or (now - datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    after = not_on_or_after or (now + datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assertion_id = "_" + uuid.uuid4().hex

    ET.register_namespace("saml", SAML_NS)
    ET.register_namespace("ds", DSIG_NS)

    # Build the SAML assertion (unsigned parts first, digest computed on it).
    root = ET.Element(f"{{{SAML_NS}}}Assertion", {
        "ID": assertion_id,
        "Version": "2.0",
        "IssueInstant": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, nsmap={"saml": SAML_NS, "ds": DSIG_NS})
    issuer_el = ET.SubElement(root, f"{{{SAML_NS}}}Issuer")
    issuer_el.text = issuer

    subject = ET.SubElement(root, f"{{{SAML_NS}}}Subject")
    name_id = ET.SubElement(subject, f"{{{SAML_NS}}}NameID")
    name_id.text = email
    subj_confirm = ET.SubElement(subject, f"{{{SAML_NS}}}SubjectConfirmation")
    subj_confirm.set("Method", "urn:oasis:names:tc:SAML:2.0:cm:bearer")

    conditions = ET.SubElement(root, f"{{{SAML_NS}}}Conditions")
    conditions.set("NotBefore", before)
    conditions.set("NotOnOrAfter", after)

    statement = ET.SubElement(root, f"{{{SAML_NS}}}AttributeStatement")
    for name, value in (("username", username), ("role", role), ("email", email)):
        attr = ET.SubElement(statement, f"{{{SAML_NS}}}Attribute")
        attr.set("Name", name)
        val_el = ET.SubElement(attr, f"{{{SAML_NS}}}AttributeValue")
        val_el.text = value

    # ---- Build signature over the assertion ----
    signed_info = ET.Element(f"{{{DSIG_NS}}}SignedInfo")
    canon_m = ET.SubElement(signed_info, f"{{{DSIG_NS}}}CanonicalizationMethod")
    canon_m.set("Algorithm", "http://www.w3.org/2001/10/xml-exc-c14n#")
    sig_method = ET.SubElement(signed_info, f"{{{DSIG_NS}}}SignatureMethod")
    sig_method.set("Algorithm", "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
    reference = ET.SubElement(signed_info, f"{{{DSIG_NS}}}Reference", {"URI": f"#{assertion_id}"})
    transforms = ET.SubElement(reference, f"{{{DSIG_NS}}}Transforms")
    t1 = ET.SubElement(transforms, f"{{{DSIG_NS}}}Transform")
    t1.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#enveloped-signature")
    t2 = ET.SubElement(transforms, f"{{{DSIG_NS}}}Transform")
    t2.set("Algorithm", "http://www.w3.org/2001/10/xml-exc-c14n#")
    digest_m = ET.SubElement(reference, f"{{{DSIG_NS}}}DigestMethod")
    digest_m.set("Algorithm", "http://www.w3.org/2001/04/xmlenc#sha256")

    # Reference digest: canonicalize the assertion (signature not yet embedded,
    # which equals the enveloped-signature transform the verifier reproduces).
    assertion_canon = _canonicalize(root)
    digest_val = ET.SubElement(reference, f"{{{DSIG_NS}}}DigestValue")
    digest_val.text = base64.b64encode(_hash_bytes(assertion_canon)).decode("ascii")

    # SignatureValue over canonicalized SignedInfo.
    signed_info_canon = _canonicalize(signed_info)
    signature_bytes = key.sign(signed_info_canon, padding.PKCS1v15(), hashes.SHA256())

    signature = ET.SubElement(root, f"{{{DSIG_NS}}}Signature")
    signature.insert(0, signed_info)
    sig_value = ET.SubElement(signature, f"{{{DSIG_NS}}}SignatureValue")
    sig_value.text = base64.b64encode(signature_bytes).decode("ascii")

    # Embed the signing cert in KeyInfo (the verifier compares against configured cert).
    key_info = ET.SubElement(signature, f"{{{DSIG_NS}}}KeyInfo")
    x509_data = ET.SubElement(key_info, f"{{{DSIG_NS}}}X509Data")
    cert_el = ET.SubElement(x509_data, f"{{{DSIG_NS}}}X509Certificate")
    cert_el.text = ""

    # Wrap in a Response element.
    PROTO_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
    proto = ET.Element(
        f"{{{PROTO_NS}}}Response",
        {
            "ID": "_resp_" + uuid.uuid4().hex,
            "Version": "2.0",
            "IssueInstant": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        nsmap={"samlp": PROTO_NS, "saml": SAML_NS, "ds": DSIG_NS},
    )
    resp_issuer = ET.SubElement(proto, f"{{{SAML_NS}}}Issuer")
    resp_issuer.text = issuer
    proto.append(root)
    # The digest + signature were computed on the assertion subtree alone; the
    # reference targets the Assertion by ID, which keeps the verification valid.

    if tamper_after_signing:
        tamper_after_signing(proto)

    if omit_signature:
        for el in proto.iter():
            if el.tag == f"{{{DSIG_NS}}}Signature":
                el.getparent().remove(el)

    raw = ET.tostring(proto, encoding="unicode")
    return base64.b64encode(raw.encode("utf-8")).decode("utf-8")


def _config_cert(key: RSAPrivateKey) -> str:
    """Build the PEM used as the configured IdP cert, matching a key pair."""
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "clarix-test-idp")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")


class TestEnterpriseSSOService:
    def test_save_and_get_sso_config(self, db_session, seeded_db):
        config = EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso/saml",
            protocol="SAML2",
            enabled=True,
            auto_provision=True,
            default_role="ComplianceOfficer",
        )
        assert config.organization_id == "test_org"
        assert config.enabled is True
        retrieved = EnterpriseSSOService.get_config(db_session, "test_org")
        assert retrieved is not None
        assert retrieved.idp_issuer == SAMPLE_ISSUER

    def test_verify_and_parse_valid_signed_assertion(self, db_session, seeded_db):
        """A correctly-signed assertion is accepted and parsed."""
        key, _ = _make_cert()
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso",
            idp_certificate=_config_cert(key),
            enabled=True,
            auto_provision=True,
            default_role="Reviewer",
        )

        response_b64 = build_signed_saml_response(key=key)
        parsed = EnterpriseSSOService.verify_and_parse_saml_assertion(
            db_session, "test_org", response_b64
        )
        assert parsed["email"] == "sarah.compliance@enterprise.com"
        assert parsed["username"] == "sarah_c"
        assert parsed["role"] == "ComplianceOfficer"

    def test_unsigned_assertion_rejected(self, db_session, seeded_db):
        """An assertion with no XML Signature must be rejected (auth-bypass fix)."""
        key, _ = _make_cert()
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso",
            idp_certificate=_config_cert(key),
            enabled=True,
            auto_provision=True,
        )
        response_b64 = build_signed_saml_response(key=key, omit_signature=True)
        try:
            EnterpriseSSOService.verify_and_parse_saml_assertion(db_session, "test_org", response_b64)
            assert False, "Unsigned assertion must be rejected."
        except SamlVerificationError:
            pass

    def test_tampered_assertion_rejected(self, db_session, seeded_db):
        """Changing an attribute value post-signing must fail the digest check."""
        key, _ = _make_cert()
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso",
            idp_certificate=_config_cert(key),
            enabled=True,
            auto_provision=True,
        )

        def tamper(root):
            el = root.find(f".//{{{'urn:oasis:names:tc:SAML:2.0:assertion'}}}AttributeValue")
            el.text = "attacker@evil.com"

        response_b64 = build_signed_saml_response(key=key, tamper_after_signing=tamper)
        try:
            EnterpriseSSOService.verify_and_parse_saml_assertion(db_session, "test_org", response_b64)
            assert False, "Tampered assertion must be rejected."
        except SamlVerificationError:
            pass

    def test_wrong_issuer_rejected(self, db_session, seeded_db):
        """An assertion from an unconfigured IdP must be rejected."""
        key, _ = _make_cert()
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso",
            idp_certificate=_config_cert(key),
            enabled=True,
            auto_provision=True,
        )
        response_b64 = build_signed_saml_response(key=key, issuer="https://evil.example.com/idp")
        try:
            EnterpriseSSOService.verify_and_parse_saml_assertion(db_session, "test_org", response_b64)
            assert False, "Assertion from wrong issuer must be rejected."
        except SamlVerificationError:
            pass

    def test_assert_sso_secure_refuses_no_cert(self, db_session, seeded_db):
        """SSO without a configured IdP certificate must be refused up-front."""
        EnterpriseSSOService.save_config(
            db_session,
            org_id="test_org",
            idp_issuer=SAMPLE_ISSUER,
            idp_sso_url="https://idp.okta.com/app/clarix/sso",
            idp_certificate=None,
            enabled=True,
            auto_provision=True,
        )
        cfg = EnterpriseSSOService.get_config(db_session, "test_org")
        try:
            EnterpriseSSOService.assert_sso_secure(cfg)
            assert False, "SSO without cert must not be 'secure'."
        except SamlVerificationError:
            pass

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

        db_user = db_session.query(User).filter(User.email == "new_sso_user@enterprise.com").first()
        assert db_user is not None