from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import or_, select

from app.database import SessionDep
from app.models import (
    Archive,
    ArchiveCategory,
    ArchiveCreate,
    ArchivePublic,
    ArchiveStatus,
    ArchiveUpdate,
    Page,
    User,
)
from app.pagination import paginate
from app.security import ADMIN_DEP
from app.utils import slugify, utcnow

router = APIRouter(prefix="/archives", tags=["archives"])


@router.get("/", response_model=Page[ArchivePublic])
def list_archives(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Search title or slug")] = None,
    status_filter: Annotated[ArchiveStatus | None, Query(alias="status")] = None,
    archive_category_id: Annotated[int | None, Query()] = None,
    author_id: Annotated[int | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    statement = select(Archive)
    if q:
        like = f"%{q}%"
        statement = statement.where(
            or_(Archive.title.like(like), Archive.slug.like(like))
        )
    if status_filter is not None:
        statement = statement.where(Archive.status == status_filter)
    if archive_category_id is not None:
        statement = statement.where(Archive.archive_category_id == archive_category_id)
    if author_id is not None:
        statement = statement.where(Archive.author_id == author_id)
    statement = statement.order_by(Archive.id.desc())
    return paginate(session, statement, offset, limit)


@router.get("/{archive_id}", response_model=ArchivePublic)
def get_archive(archive_id: int, session: SessionDep) -> Archive:
    archive = session.get(Archive, archive_id)
    if archive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found")
    return archive


@router.get("/slug/{slug}", response_model=ArchivePublic)
def get_archive_by_slug(slug: str, session: SessionDep) -> Archive:
    archive = session.exec(select(Archive).where(Archive.slug == slug)).first()
    if archive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found")
    archive.view_count += 1
    session.add(archive)
    session.commit()
    session.refresh(archive)
    return archive


@router.post("/", response_model=ArchivePublic, status_code=status.HTTP_201_CREATED, dependencies=ADMIN_DEP)
def create_archive(payload: ArchiveCreate, session: SessionDep) -> Archive:
    if session.get(User, payload.author_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown author_id: {payload.author_id}",
        )
    if payload.archive_category_id is not None:
        if session.get(ArchiveCategory, payload.archive_category_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown archive_category_id: {payload.archive_category_id}",
            )
    data = payload.model_dump()
    if not data.get("slug"):
        data["slug"] = slugify(data["title"])
    if not data["slug"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot derive slug from title; provide slug explicitly",
        )
    if data.get("status") == ArchiveStatus.published and data.get("published_at") is None:
        data["published_at"] = utcnow()
    archive = Archive(**data)
    session.add(archive)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        )
    session.refresh(archive)
    return archive


@router.patch("/{archive_id}", response_model=ArchivePublic, dependencies=ADMIN_DEP)
def update_archive(
    archive_id: int, payload: ArchiveUpdate, session: SessionDep
) -> Archive:
    archive = session.get(Archive, archive_id)
    if archive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found")
    data = payload.model_dump(exclude_unset=True)
    if "archive_category_id" in data and data["archive_category_id"] is not None:
        if session.get(ArchiveCategory, data["archive_category_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown archive_category_id: {data['archive_category_id']}",
            )
    if "slug" in data and not data["slug"]:
        title = data.get("title", archive.title)
        data["slug"] = slugify(title)
        if not data["slug"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot derive slug from title; provide slug explicitly",
            )
    new_status = data.get("status")
    if (
        new_status == ArchiveStatus.published
        and archive.status != ArchiveStatus.published
        and archive.published_at is None
        and "published_at" not in data
    ):
        data["published_at"] = utcnow()
    for key, value in data.items():
        setattr(archive, key, value)
    archive.updated_at = utcnow()
    session.add(archive)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="slug already exists"
        )
    session.refresh(archive)
    return archive


@router.delete("/{archive_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ADMIN_DEP)
def delete_archive(archive_id: int, session: SessionDep) -> None:
    archive = session.get(Archive, archive_id)
    if archive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive not found")
    session.delete(archive)
    session.commit()
