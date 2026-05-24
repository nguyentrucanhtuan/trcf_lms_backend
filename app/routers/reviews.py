from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Course,
    Enrollment,
    EnrollmentStatus,
    Page,
    Review,
    ReviewCreate,
    ReviewPublic,
    ReviewUpdate,
    Student,
)
from app.pagination import paginate
from app.security import (
    CurrentUserDep,
    VerifiedUserDep,
    assert_acts_for_student,
)
from app.utils import utcnow

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/", response_model=Page[ReviewPublic])
def list_reviews(
    session: SessionDep,
    course_id: Annotated[int | None, Query()] = None,
    student_id: Annotated[int | None, Query()] = None,
    published_only: Annotated[bool, Query()] = True,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(Review)
    if course_id is not None:
        statement = statement.where(Review.course_id == course_id)
    if student_id is not None:
        statement = statement.where(Review.student_id == student_id)
    if published_only:
        statement = statement.where(Review.is_published.is_(True))
    statement = statement.order_by(Review.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{review_id}", response_model=ReviewPublic)
def get_review(review_id: int, session: SessionDep) -> Review:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


@router.post("/", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate, session: SessionDep, current_user: VerifiedUserDep
) -> Review:
    assert_acts_for_student(session, current_user, payload.student_id)
    if session.get(Student, payload.student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown student_id: {payload.student_id}",
        )
    if session.get(Course, payload.course_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown course_id: {payload.course_id}",
        )
    enrollment = session.exec(
        select(Enrollment).where(
            Enrollment.student_id == payload.student_id,
            Enrollment.course_id == payload.course_id,
            Enrollment.status == EnrollmentStatus.active,
        )
    ).first()
    if enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student must be actively enrolled to review this course",
        )
    review = Review.model_validate(payload)
    session.add(review)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student has already reviewed this course",
        )
    session.refresh(review)
    return review


@router.patch("/{review_id}", response_model=ReviewPublic)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Review:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    assert_acts_for_student(session, current_user, review.student_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(review, key, value)
    review.updated_at = utcnow()
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int, session: SessionDep, current_user: CurrentUserDep
) -> None:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    assert_acts_for_student(session, current_user, review.student_id)
    session.delete(review)
    session.commit()
