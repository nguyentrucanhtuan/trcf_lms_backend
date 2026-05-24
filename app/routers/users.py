from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import SessionDep
from app.models import Page, User, UserCreate, UserPublic, UserRole, UserUpdate
from app.pagination import paginate
from app.security import ADMIN_DEP, hash_password
from app.utils import utcnow

router = APIRouter(prefix="/users", tags=["users"], dependencies=ADMIN_DEP)


@router.get("/", response_model=Page[UserPublic])
def list_users(
    session: SessionDep,
    email: Annotated[str | None, Query(description="Exact-match email lookup")] = None,
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(User)
    if email is not None:
        statement = statement.where(User.email == email)
    if role is not None:
        statement = statement.where(User.role == role)
    if is_active is not None:
        statement = statement.where(User.is_active == is_active)
    statement = statement.order_by(User.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{user_id}", response_model=UserPublic)
def get_user(user_id: int, session: SessionDep) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    user = User(
        email=payload.email,
        role=payload.role,
        is_active=payload.is_active,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserPublic)
def update_user(user_id: int, payload: UserUpdate, session: SessionDep) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        plain = data.pop("password")
        if plain is not None:
            user.password_hash = hash_password(plain)
    for key, value in data.items():
        setattr(user, key, value)
    user.updated_at = utcnow()
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        )
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, session: SessionDep) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    session.delete(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is referenced by a student profile; delete the student first",
        )
