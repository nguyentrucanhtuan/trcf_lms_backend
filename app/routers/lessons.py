from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Course,
    Lesson,
    LessonCreate,
    LessonProgress,
    LessonPublic,
    LessonUpdate,
    Section,
)
from app.security import ADMIN_DEP, OptionalUserDep, caller_is_enrolled
from app.utils import utcnow

router = APIRouter(prefix="/lessons", tags=["lessons"])

_LOCKED_FIELDS = ("content", "video_url")


def _strip_protected_fields(lesson: Lesson) -> dict:
    data = LessonPublic.model_validate(lesson, from_attributes=True).model_dump()
    for f in _LOCKED_FIELDS:
        data[f] = None
    return data


def _serialize_for_caller(
    session, user, lesson: Lesson, course_id_for_access: int
) -> dict | Lesson:
    if lesson.is_preview or caller_is_enrolled(session, user, course_id_for_access):
        return lesson
    return _strip_protected_fields(lesson)


@router.get("/", response_model=list[LessonPublic])
def list_lessons(
    session: SessionDep,
    user: OptionalUserDep,
    course_id: Annotated[int, Query(description="Filter by course id")],
    section_id: Annotated[int | None, Query(description="Filter by section id")] = None,
    no_section: Annotated[bool, Query(description="Only lessons without a section")] = False,
    is_published: Annotated[bool | None, Query()] = None,
) -> list:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    statement = select(Lesson).where(Lesson.course_id == course_id)
    if no_section:
        statement = statement.where(Lesson.section_id.is_(None))
    elif section_id is not None:
        statement = statement.where(Lesson.section_id == section_id)
    if is_published is not None:
        statement = statement.where(Lesson.is_published == is_published)
    statement = statement.order_by(Lesson.position, Lesson.id)
    lessons = list(session.exec(statement).all())
    enrolled = caller_is_enrolled(session, user, course_id)
    if enrolled:
        return lessons
    return [
        lesson if lesson.is_preview else _strip_protected_fields(lesson)
        for lesson in lessons
    ]


@router.get("/{lesson_id}", response_model=LessonPublic)
def get_lesson(lesson_id: int, session: SessionDep, user: OptionalUserDep):
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return _serialize_for_caller(session, user, lesson, lesson.course_id)


@router.post("/", response_model=LessonPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_lesson(payload: LessonCreate, session: SessionDep) -> Lesson:
    if session.get(Course, payload.course_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown course_id: {payload.course_id}",
        )
    if payload.section_id is not None:
        section = session.get(Section, payload.section_id)
        if section is None or section.course_id != payload.course_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="section_id does not belong to course_id",
            )
    lesson = Lesson.model_validate(payload)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.patch("/{lesson_id}", response_model=LessonPublic, dependencies=ADMIN_DEP)
def update_lesson(
    lesson_id: int, payload: LessonUpdate, session: SessionDep
) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    data = payload.model_dump(exclude_unset=True)
    if "section_id" in data:
        new_section_id = data["section_id"]
        if new_section_id is not None:
            section = session.get(Section, new_section_id)
            if section is None or section.course_id != lesson.course_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="section_id does not belong to lesson's course",
                )
    for key, value in data.items():
        setattr(lesson, key, value)
    lesson.updated_at = utcnow()
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_lesson(lesson_id: int, session: SessionDep) -> None:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    for progress in session.exec(
        select(LessonProgress).where(LessonProgress.lesson_id == lesson_id)
    ).all():
        session.delete(progress)
    session.flush()
    session.delete(lesson)
    session.commit()
