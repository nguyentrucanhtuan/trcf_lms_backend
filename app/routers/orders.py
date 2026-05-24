import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import SessionDep
from app.models import (
    Coupon,
    Course,
    Enrollment,
    EnrollmentStatus,
    Order,
    OrderCreate,
    OrderItem,
    OrderPublic,
    OrderUpdate,
    Page,
    PaymentMethod,
    PaymentStatus,
    Student,
)
from app.pagination import paginate
from app.routers.coupons import compute_discount, increment_coupon_usage, resolve_coupon
from app.security import (
    ADMIN_DEP,
    CurrentUserDep,
    VerifiedUserDep,
    assert_acts_for_student,
    enforce_student_filter,
)
from app.utils import utcnow

router = APIRouter(prefix="/orders", tags=["orders"])


def _apply_paid_side_effects(session: Session, order: Order) -> None:
    if order.paid_at is None:
        order.paid_at = utcnow()
    for item in order.items:
        existing = session.exec(
            select(Enrollment).where(
                Enrollment.student_id == order.student_id,
                Enrollment.course_id == item.course_id,
            )
        ).first()
        if existing is None:
            session.add(
                Enrollment(
                    student_id=order.student_id,
                    course_id=item.course_id,
                    status=EnrollmentStatus.active,
                )
            )
        elif existing.status != EnrollmentStatus.active:
            existing.status = EnrollmentStatus.active
            existing.updated_at = utcnow()
            session.add(existing)


@router.get("/", response_model=Page[OrderPublic])
def list_orders(
    session: SessionDep,
    current_user: CurrentUserDep,
    student_id: Annotated[int | None, Query()] = None,
    payment_status: Annotated[PaymentStatus | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    student_id = enforce_student_filter(session, current_user, student_id)
    statement = select(Order)
    if student_id is not None:
        statement = statement.where(Order.student_id == student_id)
    if payment_status is not None:
        statement = statement.where(Order.payment_status == payment_status)
    statement = statement.order_by(Order.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{order_id}", response_model=OrderPublic)
def get_order(
    order_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    assert_acts_for_student(session, current_user, order.student_id)
    return order


@router.get("/code/{order_code}", response_model=OrderPublic)
def get_order_by_code(
    order_code: str, session: SessionDep, current_user: CurrentUserDep
) -> Order:
    order = session.exec(select(Order).where(Order.order_code == order_code)).first()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    assert_acts_for_student(session, current_user, order.student_id)
    return order


@router.post("/", response_model=OrderPublic, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate, session: SessionDep, current_user: VerifiedUserDep
) -> Order:
    assert_acts_for_student(session, current_user, payload.student_id)
    if session.get(Student, payload.student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown student_id: {payload.student_id}",
        )
    method = session.get(PaymentMethod, payload.payment_method_id)
    if method is None or not method.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payment_method_id is unknown or inactive",
        )
    course_ids = [item.course_id for item in payload.items]
    if len(course_ids) != len(set(course_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate course_id in items",
        )
    courses = list(
        session.exec(select(Course).where(Course.id.in_(course_ids))).all()
    )
    missing = set(course_ids) - {c.id for c in courses}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown course_ids: {sorted(missing)}",
        )
    subtotal = sum(item.unit_price for item in payload.items)
    discount_amount = 0
    coupon_obj: Coupon | None = None
    if payload.coupon_code:
        coupon_obj = resolve_coupon(session, payload.coupon_code)
        discount_amount = compute_discount(coupon_obj, subtotal)
    order = Order(
        order_code=str(uuid.uuid4()),
        student_id=payload.student_id,
        payment_method_id=payload.payment_method_id,
        notes=payload.notes,
        subtotal_amount=subtotal,
        discount_amount=discount_amount,
        total_amount=max(subtotal - discount_amount, 0),
        coupon_id=coupon_obj.id if coupon_obj else None,
    )
    order.items = [
        OrderItem(course_id=item.course_id, unit_price=item.unit_price)
        for item in payload.items
    ]
    session.add(order)
    if coupon_obj is not None:
        increment_coupon_usage(session, coupon_obj)
    session.commit()
    session.refresh(order)
    return order


@router.patch("/{order_id}", response_model=OrderPublic, dependencies=ADMIN_DEP)
def update_order(order_id: int, payload: OrderUpdate, session: SessionDep) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    data = payload.model_dump(exclude_unset=True)
    if "payment_method_id" in data:
        method = session.get(PaymentMethod, data["payment_method_id"])
        if method is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unknown payment_method_id",
            )
    new_status = data.get("payment_status")
    if (
        new_status is not None
        and order.payment_status == PaymentStatus.paid
        and new_status != PaymentStatus.paid
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot transition a paid order to another state via PATCH; refund instead",
        )
    will_transition_to_paid = (
        new_status == PaymentStatus.paid and order.payment_status != PaymentStatus.paid
    )
    for key, value in data.items():
        setattr(order, key, value)
    order.updated_at = utcnow()
    if will_transition_to_paid:
        _apply_paid_side_effects(session, order)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.post("/{order_id}/mark-paid", response_model=OrderPublic, dependencies=ADMIN_DEP)
def mark_order_paid(
    order_id: int,
    session: SessionDep,
    provider_txn_id: Annotated[str | None, Query()] = None,
) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.payment_status == PaymentStatus.paid:
        return order
    if order.payment_status in (PaymentStatus.refunded, PaymentStatus.cancelled):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot mark {order.payment_status.value} order as paid",
        )
    order.payment_status = PaymentStatus.paid
    if provider_txn_id is not None:
        order.provider_txn_id = provider_txn_id
    order.updated_at = utcnow()
    _apply_paid_side_effects(session, order)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.post("/{order_id}/cancel", response_model=OrderPublic)
def cancel_order(
    order_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    assert_acts_for_student(session, current_user, order.student_id)
    if order.payment_status == PaymentStatus.paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel a paid order; refund it instead",
        )
    order.payment_status = PaymentStatus.cancelled
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_order(order_id: int, session: SessionDep) -> None:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.payment_status == PaymentStatus.paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a paid order",
        )
    for item in session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all():
        session.delete(item)
    session.delete(order)
    session.commit()
