from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    PaymentMethod,
    PaymentMethodCreate,
    PaymentMethodPublic,
    PaymentMethodUpdate,
)
from app.security import ADMIN_DEP
from app.utils import utcnow

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])


@router.get("/", response_model=list[PaymentMethodPublic])
def list_payment_methods(
    session: SessionDep,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[PaymentMethod]:
    statement = select(PaymentMethod)
    if is_active is not None:
        statement = statement.where(PaymentMethod.is_active == is_active)
    statement = statement.order_by(PaymentMethod.display_order, PaymentMethod.id)
    return list(session.exec(statement).all())


@router.get("/{method_id}", response_model=PaymentMethodPublic)
def get_payment_method(method_id: int, session: SessionDep) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    return method


@router.post("/", response_model=PaymentMethodPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_payment_method(
    payload: PaymentMethodCreate, session: SessionDep
) -> PaymentMethod:
    method = PaymentMethod.model_validate(payload)
    session.add(method)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code already exists",
        )
    session.refresh(method)
    return method


@router.patch("/{method_id}", response_model=PaymentMethodPublic, dependencies=ADMIN_DEP)
def update_payment_method(
    method_id: int, payload: PaymentMethodUpdate, session: SessionDep
) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(method, key, value)
    method.updated_at = utcnow()
    session.add(method)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code already exists",
        )
    session.refresh(method)
    return method


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_payment_method(method_id: int, session: SessionDep) -> None:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
    session.delete(method)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment method is referenced by existing orders",
        )
