from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    Course,
    CoursePublic,
    Enrollment,
    EnrollmentCreate,
    EnrollmentPublic,
    EnrollmentStatus,
    EnrollmentUpdate,
    Page,
    Student,
    StudentPublic,
)
from app.pagination import paginate
from app.security import (
    ADMIN_DEP,
    CurrentUserDep,
    assert_acts_for_student,
    enforce_student_filter,
)
from app.utils import utcnow

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


def _active_filter(stmt):
    now = utcnow()
    return stmt.where(
        Enrollment.status == EnrollmentStatus.active,
        or_(Enrollment.expires_at.is_(None), Enrollment.expires_at > now),
    )


@router.get("/", response_model=Page[EnrollmentPublic])
def list_enrollments(
    session: SessionDep,
    current_user: CurrentUserDep,
    student_id: Annotated[int | None, Query()] = None,
    course_id: Annotated[int | None, Query()] = None,
    status_filter: Annotated[EnrollmentStatus | None, Query(alias="status")] = None,
    active_only: Annotated[bool, Query(description="Only currently effective enrollments")] = False,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    student_id = enforce_student_filter(session, current_user, student_id)
    statement = select(Enrollment)
    if student_id is not None:
        statement = statement.where(Enrollment.student_id == student_id)
    if course_id is not None:
        statement = statement.where(Enrollment.course_id == course_id)
    if status_filter is not None:
        statement = statement.where(Enrollment.status == status_filter)
    if active_only:
        statement = _active_filter(statement)
    statement = statement.order_by(Enrollment.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{enrollment_id}", response_model=EnrollmentPublic)
def get_enrollment(
    enrollment_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Enrollment:
    enrollment = session.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    assert_acts_for_student(session, current_user, enrollment.student_id)
    return enrollment


@router.post("/", response_model=EnrollmentPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_enrollment(payload: EnrollmentCreate, session: SessionDep) -> Enrollment:
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
    enrollment = Enrollment.model_validate(payload)
    session.add(enrollment)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled in this course",
        )
    session.refresh(enrollment)
    return enrollment


@router.patch("/{enrollment_id}", response_model=EnrollmentPublic, dependencies=ADMIN_DEP)
def update_enrollment(
    enrollment_id: int, payload: EnrollmentUpdate, session: SessionDep
) -> Enrollment:
    enrollment = session.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(enrollment, key, value)
    enrollment.updated_at = utcnow()
    session.add(enrollment)
    session.commit()
    session.refresh(enrollment)
    return enrollment


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_enrollment(enrollment_id: int, session: SessionDep) -> None:
    enrollment = session.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
    session.delete(enrollment)
    session.commit()


@router.get("/students/{student_id}/courses", response_model=list[CoursePublic])
def list_courses_for_student(
    student_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    active_only: Annotated[bool, Query()] = True,
) -> list[Course]:
    assert_acts_for_student(session, current_user, student_id)
    if session.get(Student, student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    statement = (
        select(Course).join(Enrollment).where(Enrollment.student_id == student_id)
    )
    if active_only:
        statement = _active_filter(statement)
    return list(session.exec(statement).all())


@router.get("/courses/{course_id}/students", response_model=list[StudentPublic], dependencies=ADMIN_DEP)
def list_students_for_course(
    course_id: int,
    session: SessionDep,
    active_only: Annotated[bool, Query()] = True,
) -> list[Student]:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    statement = (
        select(Student).join(Enrollment).where(Enrollment.course_id == course_id)
    )
    if active_only:
        statement = _active_filter(statement)
    return list(session.exec(statement).all())
