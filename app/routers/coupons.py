from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import SessionDep
from app.models import (
    Coupon,
    CouponCreate,
    CouponPublic,
    CouponType,
    CouponUpdate,
    Page,
)
from app.pagination import paginate
from app.security import ADMIN_DEP
from app.utils import utcnow

router = APIRouter(prefix="/coupons", tags=["coupons"])


def increment_coupon_usage(session: Session, coupon: Coupon) -> None:
    """Atomically bump used_count, respecting max_uses. Raises 422 if exhausted."""
    stmt = (
        update(Coupon)
        .where(Coupon.id == coupon.id)
        .where(
            or_(Coupon.max_uses.is_(None), Coupon.used_count < Coupon.max_uses)
        )
        .values(used_count=Coupon.used_count + 1)
    )
    result = session.exec(stmt)
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon usage limit reached",
        )


def resolve_coupon(session: Session, code: str) -> Coupon:
    coupon = session.exec(select(Coupon).where(Coupon.code == code)).first()
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown coupon code: {code}",
        )
    if not coupon.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon is not active",
        )
    now = utcnow()
    if coupon.valid_from is not None and now < coupon.valid_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon is not yet valid",
        )
    if coupon.valid_to is not None and now > coupon.valid_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon has expired",
        )
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon usage limit reached",
        )
    return coupon


def compute_discount(coupon: Coupon, subtotal: int) -> int:
    if coupon.discount_type == CouponType.percent:
        value = min(coupon.discount_value, 100)
        return subtotal * value // 100
    return min(coupon.discount_value, subtotal)


@router.get("/", response_model=Page[CouponPublic], dependencies=ADMIN_DEP)
def list_coupons(
    session: SessionDep,
    is_active: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(Coupon)
    if is_active is not None:
        statement = statement.where(Coupon.is_active == is_active)
    statement = statement.order_by(Coupon.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{coupon_id}", response_model=CouponPublic, dependencies=ADMIN_DEP)
def get_coupon(coupon_id: int, session: SessionDep) -> Coupon:
    coupon = session.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    return coupon


@router.post("/validate", response_model=dict)
def validate_coupon(
    session: SessionDep,
    code: Annotated[str, Query()],
    subtotal: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    coupon = resolve_coupon(session, code)
    return {
        "code": coupon.code,
        "discount_type": coupon.discount_type.value,
        "discount_value": coupon.discount_value,
        "discount_amount": compute_discount(coupon, subtotal),
    }


@router.post("/", response_model=CouponPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_coupon(payload: CouponCreate, session: SessionDep) -> Coupon:
    if payload.discount_type == CouponType.percent and payload.discount_value > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Percent discount must be 0-100",
        )
    coupon = Coupon.model_validate(payload)
    session.add(coupon)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="code already exists"
        )
    session.refresh(coupon)
    return coupon


@router.patch("/{coupon_id}", response_model=CouponPublic, dependencies=ADMIN_DEP)
def update_coupon(
    coupon_id: int, payload: CouponUpdate, session: SessionDep
) -> Coupon:
    coupon = session.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(coupon, key, value)
    coupon.updated_at = utcnow()
    session.add(coupon)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="code already exists"
        )
    session.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_coupon(coupon_id: int, session: SessionDep) -> None:
    coupon = session.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    session.delete(coupon)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coupon is referenced by orders",
        )
