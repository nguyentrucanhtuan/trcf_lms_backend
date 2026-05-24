from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select


def paginate(session: Session, statement: Any, offset: int, limit: int) -> dict:
    count_stmt = select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
    total = session.exec(count_stmt).one()
    page_stmt = statement.offset(offset).limit(limit)
    items = list(session.exec(page_stmt).all())
    return {"items": items, "total": total, "offset": offset, "limit": limit}
