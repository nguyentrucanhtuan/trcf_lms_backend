from fastapi import APIRouter, HTTPException, Request, status
from pydantic import EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select

from app.database import SessionDep
from app.email import send_email_verify, send_password_reset
from app.models import Student, User, UserPublic, UserRole
from app.rate_limit import limiter
from app.security import (
    ACCESS_TOKEN_TTL,
    CurrentUserDep,
    create_access_token,
    create_email_verify_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.utils import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(SQLModel):
    email: EmailStr
    password: str


class RefreshRequest(SQLModel):
    refresh_token: str


class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(TokenResponse):
    user: UserPublic


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, session: SessionDep) -> LoginResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
        )
    user.last_login_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return LoginResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
        user=UserPublic.model_validate(user, from_attributes=True),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: SessionDep) -> TokenResponse:
    decoded = decode_token(payload.refresh_token, "refresh")
    user = session.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )
    if int(decoded.get("ver", 0)) != int(user.token_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )
    return TokenResponse(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUserDep) -> User:
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: CurrentUserDep, session: SessionDep) -> None:
    """Increment token_version so all previously issued tokens become invalid."""
    current_user.token_version = (current_user.token_version or 0) + 1
    current_user.updated_at = utcnow()
    session.add(current_user)
    session.commit()
    return None


class RegisterRequest(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def register(request: Request, payload: RegisterRequest, session: SessionDep) -> User:
    user = User(
        email=payload.email,
        role=UserRole.student,
        is_active=True,
        password_hash=hash_password(payload.password),
        # No email-sending infra in this deployment: auto-verify self-registered
        # students so they can immediately purchase and enroll.
        email_verified_at=utcnow(),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="email already exists"
        )
    student = Student(
        user_id=user.id,
        student_code=f"HV{user.id:06d}",
        full_name=payload.full_name,
    )
    session.add(student)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create student profile",
        )
    session.refresh(user)
    send_email_verify(user.email, create_email_verify_token(user))
    return user


class EmailRequest(SQLModel):
    email: EmailStr


class TokenOnlyRequest(SQLModel):
    token: str


class PasswordResetConfirmRequest(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=255)


@router.post("/email-verify/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
def request_email_verify(request: Request, payload: EmailRequest, session: SessionDep) -> None:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is not None and user.is_active and user.email_verified_at is None:
        send_email_verify(user.email, create_email_verify_token(user))
    return None


@router.post("/email-verify/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_email_verify(payload: TokenOnlyRequest, session: SessionDep) -> None:
    decoded = decode_token(payload.token, "email_verify")
    user = session.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
        user.updated_at = utcnow()
        session.add(user)
        session.commit()
    return None


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
def request_password_reset(request: Request, payload: EmailRequest, session: SessionDep) -> None:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is not None and user.is_active:
        send_password_reset(user.email, create_password_reset_token(user))
    return None


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest, session: SessionDep
) -> None:
    decoded = decode_token(payload.token, "password_reset")
    user = session.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    now = utcnow()
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    user.token_version = (user.token_version or 0) + 1
    user.updated_at = now
    session.add(user)
    session.commit()
    return None
