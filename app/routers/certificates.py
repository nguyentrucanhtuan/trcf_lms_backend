import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Certificate,
    CertificateCreate,
    CertificatePublic,
    Course,
    Lesson,
    LessonProgress,
    Page,
    Student,
)
from app.pagination import paginate
from app.security import (
    ADMIN_DEP,
    CurrentUserDep,
    assert_acts_for_student,
)

router = APIRouter(prefix="/certificates", tags=["certificates"])


def _all_lessons_completed(session, student_id: int, course_id: int) -> bool:
    total = list(
        session.exec(select(Lesson).where(Lesson.course_id == course_id)).all()
    )
    if not total:
        return False
    completed_ids = set(
        p.lesson_id
        for p in session.exec(
            select(LessonProgress)
            .join(Lesson)
            .where(
                Lesson.course_id == course_id,
                LessonProgress.student_id == student_id,
                LessonProgress.completed_at.is_not(None),
            )
        ).all()
    )
    return all(lesson.id in completed_ids for lesson in total)


@router.get("/", response_model=Page[CertificatePublic])
def list_certificates(
    session: SessionDep,
    current_user: CurrentUserDep,
    student_id: Annotated[int | None, Query()] = None,
    course_id: Annotated[int | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    if student_id is not None:
        assert_acts_for_student(session, current_user, student_id)
    statement = select(Certificate)
    if student_id is not None:
        statement = statement.where(Certificate.student_id == student_id)
    if course_id is not None:
        statement = statement.where(Certificate.course_id == course_id)
    statement = statement.order_by(Certificate.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{certificate_id}", response_model=CertificatePublic)
def get_certificate(
    certificate_id: int, session: SessionDep, current_user: CurrentUserDep
) -> Certificate:
    cert = session.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    assert_acts_for_student(session, current_user, cert.student_id)
    return cert


@router.get("/code/{certificate_code}", response_model=CertificatePublic)
def verify_certificate(certificate_code: str, session: SessionDep) -> Certificate:
    cert = session.exec(
        select(Certificate).where(Certificate.certificate_code == certificate_code)
    ).first()
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    return cert


@router.post("/", response_model=CertificatePublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def issue_certificate(
    payload: CertificateCreate, session: SessionDep
) -> Certificate:
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
    cert = Certificate(
        certificate_code=uuid.uuid4().hex,
        student_id=payload.student_id,
        course_id=payload.course_id,
        notes=payload.notes,
    )
    session.add(cert)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate already issued for this student and course",
        )
    session.refresh(cert)
    return cert


@router.post(
    "/auto-issue/students/{student_id}/courses/{course_id}",
    response_model=CertificatePublic,
)
def auto_issue_certificate(
    student_id: int,
    course_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> Certificate:
    assert_acts_for_student(session, current_user, student_id)
    if session.get(Student, student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    existing = session.exec(
        select(Certificate).where(
            Certificate.student_id == student_id,
            Certificate.course_id == course_id,
        )
    ).first()
    if existing is not None:
        return existing
    if not _all_lessons_completed(session, student_id, course_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Not all lessons in this course are completed",
        )
    cert = Certificate(
        certificate_code=uuid.uuid4().hex,
        student_id=student_id,
        course_id=course_id,
    )
    session.add(cert)
    session.commit()
    session.refresh(cert)
    return cert


@router.delete("/{certificate_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_certificate(certificate_id: int, session: SessionDep) -> None:
    cert = session.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")
    session.delete(cert)
    session.commit()
