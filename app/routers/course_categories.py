from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    CourseCategory,
    CourseCategoryCreate,
    CourseCategoryLink,
    CourseCategoryPublic,
    CourseCategoryUpdate,
    Page,
)
from app.pagination import paginate
from app.security import ADMIN_DEP
from app.utils import slugify, utcnow

router = APIRouter(prefix="/course-categories", tags=["course-categories"])


@router.get("/", response_model=Page[CourseCategoryPublic])
def list_course_categories(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Search by name or slug")] = None,
    is_active: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    statement = select(CourseCategory)
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(CourseCategory.name.like(like), CourseCategory.slug.like(like))
        )
    if is_active is not None:
        statement = statement.where(CourseCategory.is_active == is_active)
    statement = statement.order_by(CourseCategory.display_order, CourseCategory.id)
    return paginate(session, statement, offset, limit)


@router.get("/{category_id}", response_model=CourseCategoryPublic)
def get_course_category(category_id: int, session: SessionDep) -> CourseCategory:
    category = session.get(CourseCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course category not found")
    return category


@router.get("/slug/{slug}", response_model=CourseCategoryPublic)
def get_course_category_by_slug(slug: str, session: SessionDep) -> CourseCategory:
    category = session.exec(
        select(CourseCategory).where(CourseCategory.slug == slug)
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course category not found")
    return category


@router.post("/", response_model=CourseCategoryPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_course_category(
    payload: CourseCategoryCreate, session: SessionDep
) -> CourseCategory:
    data = payload.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(data["name"])
    if not data["slug"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot derive slug from name; provide slug explicitly",
        )
    category = CourseCategory(**data)
    session.add(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="slug already exists",
        )
    session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CourseCategoryPublic, dependencies=ADMIN_DEP)
def update_course_category(
    category_id: int, payload: CourseCategoryUpdate, session: SessionDep
) -> CourseCategory:
    category = session.get(CourseCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course category not found")
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and not data["slug"]:
        name = data.get("name", category.name)
        data["slug"] = slugify(name)
        if not data["slug"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot derive slug from name; provide slug explicitly",
            )
    for key, value in data.items():
        setattr(category, key, value)
    category.updated_at = utcnow()
    session.add(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="slug already exists",
        )
    session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_course_category(category_id: int, session: SessionDep) -> None:
    category = session.get(CourseCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course category not found")
    for link in session.exec(
        select(CourseCategoryLink).where(
            CourseCategoryLink.course_category_id == category_id
        )
    ).all():
        session.delete(link)
    session.delete(category)
    session.commit()
