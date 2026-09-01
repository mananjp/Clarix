"""
SAML 2.0 XML Signature verification.

Pure-Python + lxml implementation of the W3C XML Signature profile used by SAML
Responses (exclusive canonicalization, RSA-SHA256 / RSA-SHA1). Avoids a hard
native dependency on libxmlsec1 so it runs on Windows dev boxes, Linux, and
inside containers alike.

The IdP's *configured* signing certificate is the trust anchor: an assertion is
only accepted if its XML Signature validates against that exact certificate and
its issuer matches the configured IdP issuer.
"""

import base64
import datetime
import logging

import lxml.etree as ET
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509 import load_pem_x509_certificate

logger = logging.getLogger(__name__)

DSIG_NS = "http://www.w3.org/2000/09/xmldsig#"
SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
EXC_C14N_ALGO = "http://www.w3.org/2001/10/xml-exc-c14n#"
C14N_ALGO = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
RSA_SHA256_ALGO = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
RSA_SHA1_ALGO = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
SHA256_DIGEST_ALGO = "http://www.w3.org/2001/04/xmlenc#sha256"
SHA1_DIGEST_ALGO = "http://www.w3.org/2000/09/xmldsig#sha1"
ENVELOPED_TRANSFORM = "http://www.w3.org/2000/09/xmldsig#enveloped-signature"


class SamlVerificationError(ValueError):
    """Raised when a SAML assertion fails cryptographic verification."""


def _canonicalize(element: ET._Element) -> bytes:
    """Canonicalize an element using exclusive XML canonicalization (C14N 1.0)."""
    return ET.tostring(element, method="c14n", exclusive=True, with_comments=False)


def _load_public_key(idp_certificate_pem: str) -> RSAPublicKey:
    """Load the RSA public key from the IdP's configured X.509 certificate."""
    pem = idp_certificate_pem
    if "BEGIN CERTIFICATE" not in pem:
        pem = (
            "-----BEGIN CERTIFICATE-----\n"
            + pem.replace("\n", "").strip()
            + "\n-----END CERTIFICATE-----"
        )
    cert = load_pem_x509_certificate(pem.encode("utf-8"))
    pub = cert.public_key()
    if not isinstance(pub, RSAPublicKey):
        raise SamlVerificationError("IdP certificate public key is not RSA.")
    return pub


def _parse_datetime(value: str) -> datetime.datetime:
    """Parse SAML dateTime (ISO 8601, usually with Z offset)."""
    text = value.strip().rstrip("Z")
    if not text.endswith(("+00:00", "-00:00")):
        text += "+00:00"
    return datetime.datetime.fromisoformat(text)


def verify_saml_signature(
    saml_response_b64: str,
    idp_certificate_pem: str,
    expected_issuer: str,
    *, 
    _now: datetime.datetime | None = None,
) -> ET._Element:
    """
    Verify a Base64-encoded SAML 2.0 Response and return its root element.

    Performs, in order:
      1. XML well-formedness + presence of a ds:Signature.
      2. Verification of the XML signature (RSA over exclusive-C14N SignedInfo).
      3. Verification of every ds:Reference digest (detects post-signature tampering).
      4. Issuer match against the configured IdP.
      5. Conditions NotBefore / NotOnOrAfter window.

    Raises SamlVerificationError on any failure; never returns a tampered tree.
    """
    if not idp_certificate_pem:
        raise SamlVerificationError(
            "No IdP signing certificate configured; refusing unsigned SSO login."
        )
    if not expected_issuer:
        raise SamlVerificationError("No expected IdP issuer configured.")

    try:
        xml_bytes = base64.b64decode(saml_response_b64)
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        raise SamlVerificationError(f"Could not parse SAML Response: {e}")

    # 1. Locate the XML signature (must be present).
    signatures = root.findall(f".//{{{DSIG_NS}}}Signature")
    if not signatures:
        raise SamlVerificationError(
            "SAML Response is not signed; refusing unsigned assertion."
        )
    signature = signatures[0]

    public_key = _load_public_key(idp_certificate_pem)

    # 2. Verify the signature over SignedInfo.
    signed_info = signature.find(f"{{{DSIG_NS}}}SignedInfo")
    if signed_info is None:
        raise SamlVerificationError("SAML Signature has no SignedInfo.")
    sig_value_el = signature.find(f"{{{DSIG_NS}}}SignatureValue")
    if sig_value_el is None or not sig_value_el.text:
        raise SamlVerificationError("SAML Signature has no SignatureValue.")

    signed_info_bytes = _canonicalize(signed_info)
    sig_value = base64.b64decode(sig_value_el.text.strip())

    sig_method_el = signed_info.find(f"{{{DSIG_NS}}}SignatureMethod")
    sig_algorithm = sig_method_el.get("Algorithm") if sig_method_el is not None else None
    if sig_algorithm not in (RSA_SHA256_ALGO, RSA_SHA1_ALGO):
        raise SamlVerificationError(f"Unsupported signature algorithm: {sig_algorithm}")

    try:
        algorithm = hashes.SHA256() if sig_algorithm == RSA_SHA256_ALGO else hashes.SHA1()
        public_key.verify(sig_value, signed_info_bytes, padding.PKCS1v15(), algorithm)
    except Exception as e:
        raise SamlVerificationError(f"SAML signature verification failed: {e}")

    # 3. Verify each ds:Reference digest to catch content tampering.
    for reference in signed_info.findall(f"{{{DSIG_NS}}}Reference"):
        digest_method = reference.find(f"{{{DSIG_NS}}}DigestMethod")
        digest_value = reference.find(f"{{{DSIG_NS}}}DigestValue")
        d_algo = digest_method.get("Algorithm") if digest_method is not None else None
        if d_algo not in (SHA256_DIGEST_ALGO, SHA1_DIGEST_ALGO):
            raise SamlVerificationError(f"Unsupported digest algorithm: {d_algo}")

        target = _resolve_reference(root, reference)
        if target is None:
            raise SamlVerificationError("SAML Reference URI does not resolve in document.")

        transforms = reference.find(f"{{{DSIG_NS}}}Transforms")
        enveloped = False
        if transforms is not None:
            enveloped = any(
                t.get("Algorithm") == ENVELOPED_TRANSFORM
                for t in transforms.findall(f"{{{DSIG_NS}}}Transform")
            )
        target_bytes = _hash_target(root, target, enveloped, d_algo)

        provided = base64.b64decode(digest_value.text.strip()) if digest_value is not None and digest_value.text else None
        if provided is None or provided != target_bytes:
            raise SamlVerificationError(
                "SAML digest mismatch: assertion was modified after signing."
            )

    # 4. Issuer check.
    response_issuer = root.findtext(f".//{{{SAML_NS}}}Issuer")
    if not response_issuer or response_issuer.strip() != expected_issuer:
        raise SamlVerificationError(
            f"SAML Issuer '{response_issuer}' does not match configured IdP '{expected_issuer}'."
        )

    # 5. Conditions window.
    now = _now or datetime.datetime.now(datetime.timezone.utc)
    for conditions in root.findall(f".//{{{SAML_NS}}}Conditions"):
        not_before = conditions.get("NotBefore")
        not_on_or_after = conditions.get("NotOnOrAfter")
        if not_before and _parse_datetime(not_before) > now:
            raise SamlVerificationError("SAML assertion is not yet valid (NotBefore).")
        if not_on_or_after and _parse_datetime(not_on_or_after) < now:
            raise SamlVerificationError("SAML assertion has expired (NotOnOrAfter).")

    return root


def _resolve_reference(root: ET._Element, reference: ET._Element) -> ET._Element | None:
    """Resolve a ds:Reference URI to the element it refers to."""
    uri = reference.get("URI") or ""
    if not uri:
        return root
    if not uri.startswith("#"):
        raise SamlVerificationError(f"Unsupported SAML reference URI: {uri}")
    # SAML reference IRIs use xml:id / custom id attributes; match any attribute.
    wanted = uri[1:]
    for el in root.iter():
        for key in ("ID", "Id", "id"):
            if el.get(key) == wanted:
                return el
    return None


def _hash_target(
    root: ET._Element,
    target: ET._Element,
    enveloped: bool,
    digest_algo: str,
) -> bytes:
    """Canonicalize (and optionally strip the embedded Signature) then hash."""
    if enveloped:
        # A deep copy with any ds:Signature removed below *target*.
        target = _without_signature(root, target)
    canon = _canonicalize(target)
    dg = hashes.SHA256() if digest_algo == SHA256_DIGEST_ALGO else hashes.SHA1()
    digest = hashes.Hash(dg)
    digest.update(canon)
    return digest.finalize()


def _without_signature(root: ET._Element, target: ET._Element) -> ET._Element:
    """Return a deep copy of *target* with embedded ds:Signature elements removed.

    Required to reproduce the 'enveloped-signature' transform used when the
    assertion contains its own signature node.
    """
    copy = ET.fromstring(ET.tostring(target))
    for sig in copy.findall(f".//{{{DSIG_NS}}}Signature"):
        sig.getparent().remove(sig)
    return copy