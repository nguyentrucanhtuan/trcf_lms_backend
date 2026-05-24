import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.database import SessionDep
from app.models import Enrollment, EnrollmentStatus, Student, User, UserRole

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=7)
EMAIL_VERIFY_TOKEN_TTL = timedelta(hours=24)
PASSWORD_RESET_TOKEN_TTL = timedelta(hours=1)

TokenType = Literal["access", "refresh", "email_verify", "password_reset"]


def utcnow_naive() -> datetime:
    """Naive-UTC `datetime`, matching the rest of the schema until migration."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user: User, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": token_type,
        "ver": user.token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    return _create_token(user, "access", ACCESS_TOKEN_TTL)


def create_refresh_token(user: User) -> str:
    return _create_token(user, "refresh", REFRESH_TOKEN_TTL)


def create_email_verify_token(user: User) -> str:
    return _create_token(user, "email_verify", EMAIL_VERIFY_TOKEN_TTL)


def create_password_reset_token(user: User) -> str:
    return _create_token(user, "password_reset", PASSWORD_RESET_TOKEN_TTL)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Expected {expected_type} token",
        )
    return payload


def _check_token_alive(user: User, payload: dict[str, Any]) -> None:
    if int(payload.get("ver", 0)) != int(user.token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    pwd_changed = user.password_changed_at
    if pwd_changed is not None:
        iat = int(payload.get("iat", 0))
        if iat < int(pwd_changed.replace(tzinfo=timezone.utc).timestamp()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issued before password change",
            )


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, "access")
    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    _check_token_alive(user, payload)
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
    except HTTPException:
        return None
    user = session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    try:
        _check_token_alive(user, payload)
    except HTTPException:
        return None
    return user


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


def require_role(*allowed: UserRole):
    def _checker(user: CurrentUserDep) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in allowed]}",
            )
        return user

    return _checker


def require_admin(user: CurrentUserDep) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin only"
        )
    return user


AdminUserDep = Annotated[User, Depends(require_admin)]
ADMIN_DEP = [Depends(require_admin)]


def require_verified_email(user: CurrentUserDep) -> User:
    if user.role == UserRole.admin:
        return user
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email must be verified before this action",
        )
    return user


VerifiedUserDep = Annotated[User, Depends(require_verified_email)]


def get_caller_student_id(session: Session, user: User) -> int | None:
    student = session.exec(select(Student).where(Student.user_id == user.id)).first()
    return student.id if student else None


def assert_acts_for_student(
    session: Session, user: User, target_student_id: int
) -> None:
    if user.role == UserRole.admin:
        return
    own_id = get_caller_student_id(session, user)
    if own_id != target_student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this student's data",
        )


def enforce_student_filter(
    session: Session, user: User, requested_student_id: int | None
) -> int | None:
    """For list endpoints with optional student_id filter.

    Admin: keeps requested filter as-is.
    Non-admin: forced to own student id (raises 403 if no student profile).
    """
    if user.role == UserRole.admin:
        return requested_student_id
    own_id = get_caller_student_id(session, user)
    if own_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Non-admin caller has no student profile",
        )
    return own_id


def caller_is_enrolled(session: Session, user: User | None, course_id: int) -> bool:
    if user is None:
        return False
    if user.role == UserRole.admin:
        return True
    student_id = get_caller_student_id(session, user)
    if student_id is None:
        return False
    now = utcnow_naive()
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.active,
        )
    ).first()
    if enrollment is None:
        return False
    if enrollment.expires_at is not None and enrollment.expires_at <= now:
        return False
    return True
