import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, Request
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .config import settings
from .models import RateLimitBucket


def _key_digest(value: str) -> str:
    key = (settings.secret_key or "development-only-rate-limit-key").encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def enforce_rate_limit(
    request: Request,
    db: Session,
    *,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = int(time.time())
    window_start = now - now % window_seconds
    remote_host = request.client.host if request.client else "unknown"
    key_hash = _key_digest(f"{scope}:{remote_host}:{identity.casefold()}")
    table = RateLimitBucket.__table__
    dialect = db.get_bind().dialect.name
    values = {"key_hash": key_hash, "window_start": window_start, "hits": 1}
    if dialect == "sqlite":
        statement = sqlite_insert(table).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[table.c.key_hash],
            set_={
                "hits": case((table.c.window_start == window_start, table.c.hits + 1), else_=1),
                "window_start": window_start,
            },
        )
    elif dialect == "mysql":
        statement = mysql_insert(table).values(**values)
        statement = statement.on_duplicate_key_update(
            hits=case((table.c.window_start == window_start, table.c.hits + 1), else_=1),
            window_start=window_start,
        )
    else:
        raise RuntimeError(f"Persistent rate limiting is not configured for database dialect '{dialect}'.")
    db.execute(statement)
    if secrets.randbelow(100) == 0:
        db.execute(delete(table).where(table.c.window_start < now - 86_400))
    db.commit()
    hits = db.scalar(select(RateLimitBucket.hits).where(RateLimitBucket.key_hash == key_hash))
    if hits is not None and hits > limit:
        retry_after = max(1, window_start + window_seconds - now)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
