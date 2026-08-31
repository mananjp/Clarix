"""
Unit tests for auth module: password hashing, token creation/verification.
"""

import os
import sys
import datetime


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-do-not-use-in-production")

from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ALGORITHM,
)
from app.config import SECRET_KEY
from jose import jwt


class TestPasswordHashing:
    def test_hash_and_verify_correct(self):
        password = "MySuperSecure!123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_hash_and_verify_wrong_password(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_unique_per_call(self):
        """Two hashes of the same password should differ (salt)."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2


class TestTokenCreation:
    def test_create_token_contains_subject(self):
        token = create_access_token(data={"sub": "testuser"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

    def test_create_token_has_expiry(self):
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=datetime.timedelta(minutes=30),
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_create_token_custom_expiry(self):
        short_token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=datetime.timedelta(seconds=1),
        )
        payload = jwt.decode(short_token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_token_is_string(self):
        token = create_access_token(data={"sub": "user"})
        assert isinstance(token, str)
        assert len(token) > 20
