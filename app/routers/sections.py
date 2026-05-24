from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    Course,
    Lesson,
    Section,
    SectionCreate,
    SectionUpdate,
    SectionWithLessons,
)
from app.security import ADMIN_DEP
from app.utils import utcnow

router = APIRouter(prefix="/sections", tags=["sections"])


def _lessons_ordered(session, section_id: int) -> list[Lesson]:
    statement = (
        select(Lesson)
        .where(Lesson.section_id == section_id)
        .order_by(Lesson.position, Lesson.id)
    )
    return list(session.exec(statement).all())


@router.get("/", response_model=list[SectionWithLessons])
def list_sections(
    session: SessionDep,
    course_id: Annotated[int, Query(description="Required: list sections of this course")],
) -> list[Section]:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    statement = (
        select(Section)
        .where(Section.course_id == course_id)
        .order_by(Section.position, Section.id)
    )
    return list(session.exec(statement).all())


@router.get("/{section_id}", response_model=SectionWithLessons)
def get_section(section_id: int, session: SessionDep) -> Section:
    section = session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


@router.post("/", response_model=SectionWithLessons, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_section(payload: SectionCreate, session: SessionDep) -> Section:
    if session.get(Course, payload.course_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown course_id: {payload.course_id}",
        )
    section = Section.model_validate(payload)
    session.add(section)
    session.commit()
    session.refresh(section)
    return section


@router.patch("/{section_id}", response_model=SectionWithLessons, dependencies=ADMIN_DEP)
def update_section(
    section_id: int, payload: SectionUpdate, session: SessionDep
) -> Section:
    section = session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(section, key, value)
    section.updated_at = utcnow()
    session.add(section)
    session.commit()
    session.refresh(section)
    return section


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_section(section_id: int, session: SessionDep) -> None:
    section = session.get(Section, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    for lesson in _lessons_ordered(session, section_id):
        lesson.section_id = None
        session.add(lesson)
    session.delete(section)
    session.commit()
