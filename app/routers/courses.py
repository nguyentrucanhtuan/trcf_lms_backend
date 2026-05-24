from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    Certificate,
    Course,
    CourseCategory,
    CourseCategoryLink,
    CourseCreate,
    CourseDetail,
    CoursePublic,
    CourseStatus,
    CourseUpdate,
    Lesson,
    LessonProgress,
    Page,
    Review,
    Section,
)
from app.pagination import paginate
from app.security import ADMIN_DEP
from app.utils import slugify, utcnow

router = APIRouter(prefix="/courses", tags=["courses"])


def _resolve_categories(session, category_ids: list[int]) -> list[CourseCategory]:
    if not category_ids:
        return []
    unique_ids = list(dict.fromkeys(category_ids))
    found = list(
        session.exec(
            select(CourseCategory).where(CourseCategory.id.in_(unique_ids))
        ).all()
    )
    missing = set(unique_ids) - {c.id for c in found}
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown category_ids: {sorted(missing)}",
        )
    return found


@router.get("/", response_model=Page[CoursePublic])
def list_courses(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Search by name, code, or slug")] = None,
    status_filter: Annotated[CourseStatus | None, Query(alias="status")] = None,
    category_id: Annotated[int | None, Query(description="Filter by category id")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(Course)
    if category_id is not None:
        statement = statement.join(CourseCategoryLink).where(
            CourseCategoryLink.course_category_id == category_id
        )
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(
                Course.name.like(like),
                Course.course_code.like(like),
                Course.slug.like(like),
            )
        )
    if status_filter is not None:
        statement = statement.where(Course.status == status_filter)
    statement = statement.order_by(Course.id.desc())
    return paginate(session, statement, offset, limit)


def _build_course_detail(session, course: Course) -> dict:
    sections = list(
        session.exec(
            select(Section)
            .where(Section.course_id == course.id)
            .order_by(Section.position, Section.id)
        ).all()
    )
    section_ids = [s.id for s in sections]
    lessons_by_section: dict[int, list[Lesson]] = {sid: [] for sid in section_ids}
    loose: list[Lesson] = []
    for lesson in session.exec(
        select(Lesson)
        .where(Lesson.course_id == course.id)
        .order_by(Lesson.position, Lesson.id)
    ).all():
        if lesson.section_id is None:
            loose.append(lesson)
        elif lesson.section_id in lessons_by_section:
            lessons_by_section[lesson.section_id].append(lesson)
    data = CoursePublic.model_validate(course, from_attributes=True).model_dump()
    data["sections"] = [
        {
            **s.model_dump(),
            "lessons": [l.model_dump() for l in lessons_by_section.get(s.id, [])],
        }
        for s in sections
    ]
    data["lessons"] = [l.model_dump() for l in loose]
    return data


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, session: SessionDep) -> dict:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return _build_course_detail(session, course)


@router.get("/slug/{slug}", response_model=CourseDetail)
def get_course_by_slug(slug: str, session: SessionDep) -> dict:
    course = session.exec(select(Course).where(Course.slug == slug)).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return _build_course_detail(session, course)


@router.post("/", response_model=CoursePublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_course(payload: CourseCreate, session: SessionDep) -> Course:
    data = payload.model_dump()
    category_ids = data.pop("category_ids", None)
    if not data.get("slug"):
        data["slug"] = slugify(data["name"])
    if not data["slug"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot derive slug from name; provide slug explicitly",
        )
    course = Course(**data)
    if category_ids is not None:
        course.categories = _resolve_categories(session, category_ids)
    session.add(course)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="course_code or slug already exists",
        )
    session.refresh(course)
    return course


@router.patch("/{course_id}", response_model=CoursePublic, dependencies=ADMIN_DEP)
def update_course(
    course_id: int, payload: CourseUpdate, session: SessionDep
) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    data = payload.model_dump(exclude_unset=True)
    category_ids = data.pop("category_ids", None) if "category_ids" in data else "__skip__"
    if "slug" in data and not data["slug"]:
        name = data.get("name", course.name)
        data["slug"] = slugify(name)
        if not data["slug"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot derive slug from name; provide slug explicitly",
            )
    for key, value in data.items():
        setattr(course, key, value)
    if category_ids != "__skip__":
        course.categories = _resolve_categories(session, category_ids or [])
    course.updated_at = utcnow()
    session.add(course)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="course_code or slug already exists",
        )
    session.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_course(course_id: int, session: SessionDep) -> None:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    for progress in session.exec(
        select(LessonProgress).join(Lesson).where(Lesson.course_id == course_id)
    ).all():
        session.delete(progress)
    for review in session.exec(
        select(Review).where(Review.course_id == course_id)
    ).all():
        session.delete(review)
    for cert in session.exec(
        select(Certificate).where(Certificate.course_id == course_id)
    ).all():
        session.delete(cert)
    session.flush()
    for lesson in session.exec(
        select(Lesson).where(Lesson.course_id == course_id)
    ).all():
        session.delete(lesson)
    for section in session.exec(
        select(Section).where(Section.course_id == course_id)
    ).all():
        session.delete(section)
    course.categories.clear()
    session.flush()
    session.delete(course)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course is referenced by existing enrollments or orders",
        )
