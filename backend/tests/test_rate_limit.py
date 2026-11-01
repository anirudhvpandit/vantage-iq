import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import RateLimitBucket
from app.rate_limit import enforce_rate_limit


def make_request(address: str = "192.0.2.10") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/test",
            "raw_path": b"/test",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": (address, 12345),
            "server": ("testserver", 80),
        }
    )


def test_fixed_window_limit_persists_and_scopes_by_identity():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[RateLimitBucket.__table__])
    request = make_request()
    with Session(engine) as db:
        enforce_rate_limit(request, db, scope="test", identity="one", limit=1, window_seconds=60)
        with pytest.raises(HTTPException) as rejected:
            enforce_rate_limit(request, db, scope="test", identity="one", limit=1, window_seconds=60)
        assert rejected.value.status_code == 429
        assert "Retry-After" in rejected.value.headers
        enforce_rate_limit(request, db, scope="test", identity="two", limit=1, window_seconds=60)
        assert db.query(RateLimitBucket).count() == 2
    engine.dispose()
