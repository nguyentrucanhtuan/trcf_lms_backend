import pytest
from fastapi import HTTPException

from app.models import User, UserRole
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def _user(id_: int = 1) -> User:
    return User(
        id=id_,
        email="x@example.com",
        role=UserRole.student,
        password_hash="x",
        token_version=0,
    )


def test_password_hash_roundtrip():
    h = hash_password("hunter2!")
    assert verify_password("hunter2!", h)
    assert not verify_password("hunter3!", h)


def test_access_token_roundtrip():
    u = _user()
    token = create_access_token(u)
    decoded = decode_token(token, "access")
    assert decoded["sub"] == "1"
    assert decoded["type"] == "access"
    assert decoded["ver"] == 0


def test_token_type_mismatch_rejected():
    u = _user()
    token = create_refresh_token(u)
    with pytest.raises(HTTPException) as exc:
        decode_token(token, "access")
    assert exc.value.status_code == 401


def test_invalid_token_rejected():
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-jwt", "access")
    assert exc.value.status_code == 401
