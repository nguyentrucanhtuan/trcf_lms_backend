import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.database import run_migrations
from app.rate_limit import limiter
from app.routers import (
    archive_categories,
    archives,
    auth,
    certificates,
    coupons,
    course_categories,
    courses,
    enrollments,
    lesson_progress,
    lessons,
    orders,
    payment_methods,
    reviews,
    sections,
    students,
    uploads,
    users,
)
from app.routers.uploads import UPLOAD_DIR


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("AUTO_MIGRATE", "true").lower() != "false":
        run_migrations()
    yield


app = FastAPI(
    title="TRCF LMS API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

_cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
_allow_credentials = "*" not in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(students.router)
app.include_router(course_categories.router)
app.include_router(courses.router)
app.include_router(sections.router)
app.include_router(lessons.router)
app.include_router(enrollments.router)
app.include_router(payment_methods.router)
app.include_router(orders.router)
app.include_router(lesson_progress.router)
app.include_router(archive_categories.router)
app.include_router(archives.router)
app.include_router(coupons.router)
app.include_router(reviews.router)
app.include_router(certificates.router)
app.include_router(uploads.router)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads-static")


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
