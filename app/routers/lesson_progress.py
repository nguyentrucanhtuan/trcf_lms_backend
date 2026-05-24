from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Course,
    Lesson,
    LessonProgress,
    LessonProgressPublic,
    LessonProgressUpsert,
    Student,
)
from app.security import ADMIN_DEP, CurrentUserDep, assert_acts_for_student
from app.utils import utcnow

router = APIRouter(prefix="/lesson-progress", tags=["lesson-progress"])


@router.get("/", response_model=list[LessonProgressPublic])
def list_progress(
    session: SessionDep,
    current_user: CurrentUserDep,
    student_id: Annotated[int, Query(description="Required: student id")],
    course_id: Annotated[int | None, Query(description="Filter to lessons of this course")] = None,
    completed_only: Annotated[bool, Query()] = False,
) -> list[LessonProgress]:
    assert_acts_for_student(session, current_user, student_id)
    statement = select(LessonProgress).where(LessonProgress.student_id == student_id)
    if course_id is not None:
        statement = statement.join(Lesson).where(Lesson.course_id == course_id)
    if completed_only:
        statement = statement.where(LessonProgress.completed_at.is_not(None))
    statement = statement.order_by(LessonProgress.id.desc())
    return list(session.exec(statement).all())


@router.get("/{progress_id}", response_model=LessonProgressPublic)
def get_progress(
    progress_id: int, session: SessionDep, current_user: CurrentUserDep
) -> LessonProgress:
    progress = session.get(LessonProgress, progress_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson progress not found")
    assert_acts_for_student(session, current_user, progress.student_id)
    return progress


@router.post("/", response_model=LessonProgressPublic)
def upsert_progress(
    payload: LessonProgressUpsert, session: SessionDep, current_user: CurrentUserDep
) -> LessonProgress:
    assert_acts_for_student(session, current_user, payload.student_id)
    if session.get(Student, payload.student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown student_id: {payload.student_id}",
        )
    if session.get(Lesson, payload.lesson_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown lesson_id: {payload.lesson_id}",
        )
    progress = session.exec(
        select(LessonProgress).where(
            LessonProgress.student_id == payload.student_id,
            LessonProgress.lesson_id == payload.lesson_id,
        )
    ).first()
    now = utcnow()
    if progress is None:
        progress = LessonProgress(
            student_id=payload.student_id,
            lesson_id=payload.lesson_id,
            seconds_watched=payload.seconds_watched,
            last_seen_at=now,
        )
    else:
        if payload.seconds_watched > progress.seconds_watched:
            progress.seconds_watched = payload.seconds_watched
        progress.last_seen_at = now
        progress.updated_at = now
    if payload.mark_completed and progress.completed_at is None:
        progress.completed_at = now
    session.add(progress)
    session.commit()
    session.refresh(progress)
    return progress


@router.get(
    "/students/{student_id}/courses/{course_id}/summary",
    response_model=dict,
)
def course_progress_summary(
    student_id: int,
    course_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> dict:
    assert_acts_for_student(session, current_user, student_id)
    if session.get(Student, student_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    total_lessons = len(
        list(session.exec(select(Lesson).where(Lesson.course_id == course_id)).all())
    )
    progress_rows = list(
        session.exec(
            select(LessonProgress)
            .join(Lesson)
            .where(
                Lesson.course_id == course_id,
                LessonProgress.student_id == student_id,
            )
        ).all()
    )
    completed = sum(1 for p in progress_rows if p.completed_at is not None)
    return {
        "student_id": student_id,
        "course_id": course_id,
        "total_lessons": total_lessons,
        "started_lessons": len(progress_rows),
        "completed_lessons": completed,
        "completion_ratio": completed / total_lessons if total_lessons else 0.0,
        "total_seconds_watched": sum(p.seconds_watched for p in progress_rows),
    }


@router.delete("/{progress_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_progress(progress_id: int, session: SessionDep) -> None:
    progress = session.get(LessonProgress, progress_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson progress not found")
    session.delete(progress)
    session.commit()
