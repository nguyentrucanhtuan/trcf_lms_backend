import re
import unicodedata
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive-UTC datetime; matches existing schema columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")
