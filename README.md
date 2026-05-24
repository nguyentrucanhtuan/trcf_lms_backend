# TRCF LMS Backend

FastAPI backend cho hệ thống LMS của trường đào tạo barista TRCF.

## Stack

- **FastAPI** + `fastapi[standard]` CLI
- **SQLModel** trên SQLite (PRAGMA `foreign_keys=ON`)
- **Alembic** cho migrations (chạy tự động khi `AUTO_MIGRATE=true`)
- **PyJWT** (HS256) cho access / refresh / email-verify / password-reset token
- **bcrypt** cho password hashing
- **slowapi** cho rate limit IP-based
- **uv** làm package manager (Python ≥ 3.13)

## Setup

```bash
uv sync
uv run fastapi dev app/main.py --port 8765
```

Server lắng nghe ở `http://127.0.0.1:8765`, docs ở `/docs`.

## Biến môi trường

| Tên | Mặc định | Ghi chú |
|---|---|---|
| `JWT_SECRET` | `dev-insecure-change-me-in-production` | **Bắt buộc đổi ở production** |
| `RATE_LIMIT_ENABLED` | `true` | Set `false` để tắt khi test |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated; nếu chứa `*` → tự tắt `allow_credentials` |
| `AUTO_MIGRATE` | `true` | Set `false` để bỏ alembic upgrade trong lifespan (nên tắt khi multi-worker) |
| `FRONTEND_URL` | `http://localhost:3000` | Dùng để build verify / reset links trong email |
| `UPLOAD_DIR` | `./uploads` | Thư mục lưu file upload |
| `MAX_UPLOAD_SIZE` | `52428800` (50MB) | Max bytes per file |
| `PUBLIC_BASE_URL` | _empty_ | Prefix cho upload URL (nếu serve qua CDN/proxy) |

## Migrations

```bash
uv run alembic upgrade head             # apply all
uv run alembic revision -m "msg"        # new empty revision
uv run alembic downgrade -1             # roll back one
```

## Tests

```bash
uv run pytest -q                        # unit tests (utils, coupon, jwt)
uv run python scripts/smoke_test.py     # end-to-end against running server
```

## Cấu trúc

```
app/
  main.py            entry — registers routers, middleware, lifespan
  database.py        engine + session dep + run_migrations()
  models.py          SQLModel tables + Pydantic Create/Update/Public schemas
  security.py        JWT, password hash, role/verify deps, enrollment check
  pagination.py      generic Page[T] helper
  rate_limit.py      slowapi limiter
  email.py           email sender (stdout in dev — TODO SMTP)
  utils.py           slugify, utcnow
  routers/           17 routers (auth, users, students, courses, sections,
                     lessons, enrollments, payment_methods, orders,
                     lesson_progress, archives, archive_categories,
                     course_categories, coupons, reviews, certificates,
                     uploads)
alembic/             migration scripts
scripts/             smoke_test.py
tests/               pytest unit tests
```

## Bootstrap admin

```bash
# Đăng ký 1 student qua /auth/register, rồi promote:
sqlite3 lms.db "UPDATE user SET role='admin', email_verified_at=CURRENT_TIMESTAMP WHERE id=1"
```
