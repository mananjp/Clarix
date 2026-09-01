"""
Encryption-at-rest for uploaded source documents.

AES-256-GCM (authenticated encryption) applied transparently at the storage
layer: files on disk are always ciphertext, while ``load`` returns plaintext so
downstream integrity hashing and parsing behave identically to the unencrypted
path. GCM authentication also means any tampering with the stored bytes fails
decryption — strengthening the existing SHA-256 tamper check.

Nonce layout per file:  ``nonce (12B) || ciphertext || auth_tag (16B)``

Key sourcing (in priority order):
  1. ``ENCRYPTION_KEY`` env var — base64-encoded 32-byte key (recommended in prod)
  2. auto-generated key persisted to ``data/encryption.key`` (dev convenience);
     survives restarts because it lives on the same volume as uploads.
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import DATA_DIR

logger = logging.getLogger(__name__)

NONCE_BYTES = 12
TAG_BYTES = 16
KEY_FILE = DATA_DIR / "encryption.key"


def _load_or_create_key() -> bytes:
    """Return the AES-256 key from env or the persisted dev key file."""
    env_key = os.getenv("ENCRYPTION_KEY", "").strip()
    if env_key:
        try:
            key = base64.b64decode(env_key)
        except Exception as e:
            raise RuntimeError("ENCRYPTION_KEY is not valid base64.") from e
        if len(key) != 32:
            raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes (AES-256).")
        return key

    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
        if len(key) != 32:
            raise RuntimeError(f"Invalid encryption key file {KEY_FILE}")
        return key

    key = os.urandom(32)
    KEY_FILE.write_bytes(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    logger.warning(
        "No ENCRYPTION_KEY set; generated and persisted one at %s (dev only).",
        KEY_FILE,
    )
    return key


# Cache the key for the lifetime of the process (avoids re-reading the key file).
_KEY_CACHE: bytes | None = None


def get_encryption_key() -> bytes:
    global _KEY_CACHE
    if _KEY_CACHE is None:
        _KEY_CACHE = _load_or_create_key()
    return _KEY_CACHE


def encrypt_bytes(plaintext: bytes) -> bytes:
    """Return ``nonce || ciphertext || tag`` for *plaintext*."""
    key = get_encryption_key()
    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct


def decrypt_bytes(payload: bytes) -> bytes:
    """Decrypt a ``nonce || ciphertext || tag`` payload. Raises on tampering."""
    key = get_encryption_key()
    if len(payload) < NONCE_BYTES + TAG_BYTES:
        raise ValueError("Encrypted payload too short; file is corrupt or not encrypted.")
    nonce = payload[:NONCE_BYTES]
    ct = payload[NONCE_BYTES:]
    return AESGCM(key).decrypt(nonce, ct, None)


def is_encryption_enabled() -> bool:
    """True when encryption-at-rest is on for the local storage backend."""
    return os.getenv("ENCRYPT_AT_REST", "").strip().lower() in ("1", "true", "yes")