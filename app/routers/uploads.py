import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlmodel import SQLModel

from app.database import BACKEND_DIR
from app.security import ADMIN_DEP

UPLOAD_DIR = Path(
    os.environ.get("UPLOAD_DIR") or (BACKEND_DIR / "uploads")
).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 50 * 1024 * 1024))
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".mp4", ".webm", ".mov",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".mp3", ".wav",
    ".zip",
}

router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=ADMIN_DEP)


class UploadResponse(SQLModel):
    filename: str
    url: str
    size: int
    content_type: str | None


@router.post("/", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename"
        )
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Disallowed extension: {ext or '(none)'}",
        )
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / safe_name
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large; max {MAX_UPLOAD_SIZE} bytes",
                )
            out.write(chunk)
    url = f"/uploads/{safe_name}"
    if PUBLIC_BASE:
        url = f"{PUBLIC_BASE}{url}"
    return UploadResponse(
        filename=safe_name, url=url, size=size, content_type=file.content_type
    )


@router.delete("/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(filename: str) -> None:
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
        )
    target = (UPLOAD_DIR / filename).resolve()
    if not target.is_relative_to(UPLOAD_DIR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path"
        )
    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    target.unlink()
