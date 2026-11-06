import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AICache


def make_key(feature: str, prompt_version: str, model: str, payload: dict) -> str:
    """Stable hash of everything that determines the answer."""
    blob = json.dumps(
        {"f": feature, "v": prompt_version, "m": model, "p": payload}, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def get(db: Session, user_id: uuid.UUID, key: str) -> dict | None:
    row = db.scalar(select(AICache).where(AICache.user_id == user_id, AICache.cache_key == key))
    if row is None:
        return None
    if row.expires_at and _aware(row.expires_at) < datetime.now(UTC):
        db.delete(row)
        db.commit()
        return None
    row.hit_count += 1
    db.commit()
    return row.response


def put(
    db: Session, user_id: uuid.UUID, key: str, *, feature: str, model: str, prompt_version: str,
    response: dict, ttl_days: int,
) -> None:
    row = db.scalar(select(AICache).where(AICache.user_id == user_id, AICache.cache_key == key))
    expires = datetime.now(UTC) + timedelta(days=ttl_days) if ttl_days > 0 else None
    if row is None:
        db.add(AICache(
            user_id=user_id, cache_key=key, feature=feature, model=model, prompt_version=prompt_version,
            response=response, expires_at=expires,
        ))
    else:
        row.response, row.expires_at, row.model, row.prompt_version = response, expires, model, prompt_version
    db.commit()


def invalidate(db: Session, user_id: uuid.UUID, key: str) -> None:
    row = db.scalar(select(AICache).where(AICache.user_id == user_id, AICache.cache_key == key))
    if row:
        db.delete(row)
        db.commit()
