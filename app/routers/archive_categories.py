from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    ArchiveCategory,
    ArchiveCategoryCreate,
    ArchiveCategoryPublic,
    ArchiveCategoryUpdate,
    Page,
)
from app.pagination import paginate
from app.security import ADMIN_DEP
from app.utils import slugify, utcnow

router = APIRouter(prefix="/archive-categories", tags=["archive-categories"])


@router.get("/", response_model=Page[ArchiveCategoryPublic])
def list_archive_categories(
    session: SessionDep,
    q: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    statement = select(ArchiveCategory)
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(ArchiveCategory.name.like(like), ArchiveCategory.slug.like(like))
        )
    if is_active is not None:
        statement = statement.where(ArchiveCategory.is_active == is_active)
    statement = statement.order_by(ArchiveCategory.display_order, ArchiveCategory.id)
    return paginate(session, statement, offset, limit)


@router.get("/{category_id}", response_model=ArchiveCategoryPublic)
def get_archive_category(category_id: int, session: SessionDep) -> ArchiveCategory:
    category = session.get(ArchiveCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive category not found")
    return category


@router.get("/slug/{slug}", response_model=ArchiveCategoryPublic)
def get_archive_category_by_slug(slug: str, session: SessionDep) -> ArchiveCategory:
    category = session.exec(
        select(ArchiveCategory).where(ArchiveCategory.slug == slug)
    ).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive category not found")
    return category


@router.post("/", response_model=ArchiveCategoryPublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_archive_category(
    payload: ArchiveCategoryCreate, session: SessionDep
) -> ArchiveCategory:
    data = payload.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(data["name"])
    if not data["slug"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot derive slug from name; provide slug explicitly",
        )
    category = ArchiveCategory(**data)
    session.add(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        )
    session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=ArchiveCategoryPublic, dependencies=ADMIN_DEP)
def update_archive_category(
    category_id: int, payload: ArchiveCategoryUpdate, session: SessionDep
) -> ArchiveCategory:
    category = session.get(ArchiveCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive category not found")
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
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        )
    session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_archive_category(category_id: int, session: SessionDep) -> None:
    category = session.get(ArchiveCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive category not found")
    session.delete(category)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is referenced by archives; reassign or delete them first",
        )
