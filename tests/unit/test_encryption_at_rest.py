"""
Unit tests for encryption-at-rest (AES-256-GCM) and the encrypting storage
backend wrapper. Encryption is opt-in via ENCRYPT_AT_REST; these tests force it
on directly at the backend level so they do not depend on ambient env state.
"""

import os

import pytest

from app.services.encryption import (
    decrypt_bytes,
    encrypt_bytes,
    get_encryption_key,
)
from app.services.storage import LocalStorageBackend


@pytest.fixture()
def enc_key(monkeypatch):
    """Force a deterministic 32-byte key for the process."""
    import base64
    key = os.urandom(32)
    monkeypatch.setenv("ENCRYPTION_KEY", base64.b64encode(key).decode())
    # reset cached key so the new env value is picked up
    import app.services.encryption as enc_mod
    enc_mod._KEY_CACHE = None
    yield key
    enc_mod._KEY_CACHE = None


def test_round_trip_encrypt_decrypt(enc_key):
    plaintext = b"Sensitive PAI disclosure evidence"
    payload = encrypt_bytes(plaintext)
    assert payload != plaintext
    assert decrypt_bytes(payload) == plaintext


def test_payload_layout_nonce_and_tag(enc_key):
    payload = encrypt_bytes(b"x" * 100)
    assert len(payload) == 12 + 100 + 16  # nonce || ciphertext || tag


def test_tampered_payload_fails_decryption(enc_key):
    plaintext = b"authenticated-bytes"
    payload = bytearray(encrypt_bytes(plaintext))
    payload[-1] ^= 0x01  # flip one bit in the tag/ciphertext
    with pytest.raises(Exception):
        decrypt_bytes(bytes(payload))


def test_key_is_32_bytes(enc_key):
    assert len(get_encryption_key()) == 32


def test_encrypting_backend_round_trip(tmp_path):
    backend = LocalStorageBackend(base_dir=str(tmp_path), encrypt=True)
    key_name = "doc.pdf"
    backend.save(b"plaintext-pdf-bytes", key_name)

    # Bytes on disk must be ciphertext (no plaintext substring, length > source).
    on_disk = (tmp_path / key_name).read_bytes()
    assert b"plaintext-pdf-bytes" not in on_disk
    assert len(on_disk) > len(b"plaintext-pdf-bytes")

    # Load returns the original plaintext.
    assert backend.load(key_name) == b"plaintext-pdf-bytes"
    assert backend.exists(key_name)
    backend.delete(key_name)
    assert not backend.exists(key_name)


def test_non_encrypting_backend_unchanged(tmp_path):
    backend = LocalStorageBackend(base_dir=str(tmp_path), encrypt=False)
    backend.save(b"plaintext", "doc.txt")
    assert (tmp_path / "doc.txt").read_bytes() == b"plaintext"
    assert backend.load("doc.txt") == b"plaintext"