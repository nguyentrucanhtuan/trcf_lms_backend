from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    Page,
    Student,
    StudentCreate,
    StudentPublic,
    StudentStatus,
    StudentUpdate,
    User,
    UserRole,
)
from app.pagination import paginate
from app.security import ADMIN_DEP, CurrentUserDep, assert_acts_for_student
from app.utils import utcnow

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/", response_model=Page[StudentPublic], dependencies=ADMIN_DEP)
def list_students(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Search by name or student code")] = None,
    status_filter: Annotated[StudentStatus | None, Query(alias="status")] = None,
    user_id: Annotated[int | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(Student)
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(Student.full_name.like(like), Student.student_code.like(like))
        )
    if status_filter is not None:
        statement = statement.where(Student.status == status_filter)
    if user_id is not None:
        statement = statement.where(Student.user_id == user_id)
    statement = statement.order_by(Student.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{student_id}", response_model=StudentPublic)
def get_student(
    student_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Student:
    assert_acts_for_student(session, current_user, student_id)
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


@router.post("/", response_model=StudentPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_student(payload: StudentCreate, session: SessionDep) -> Student:
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown user_id: {payload.user_id}",
        )
    if user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"User role is '{user.role.value}', must be 'student'",
        )
    student = Student.model_validate(payload)
    session.add(student)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="student_code already exists or user already has a student profile",
        )
    session.refresh(student)
    return student


@router.patch("/{student_id}", response_model=StudentPublic, dependencies=ADMIN_DEP)
def update_student(
    student_id: int, payload: StudentUpdate, session: SessionDep
) -> Student:
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(student, key, value)
    student.updated_at = utcnow()
    session.add(student)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="student_code already exists",
        )
    session.refresh(student)
    return student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_student(student_id: int, session: SessionDep) -> None:
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    session.delete(student)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is referenced by existing enrollments or orders",
        )
