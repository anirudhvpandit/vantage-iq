from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
elif settings.database_url.startswith("mysql+pymysql://") and settings.database_ssl_ca:
    engine_options["connect_args"] = {
        "ssl": {
            "ca": settings.database_ssl_ca,
            "check_hostname": True,
            "verify_mode": "required",
        }
    }

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request):
    db = SessionLocal()
    db.info["request_id"] = getattr(request.state, "request_id", None)
    try:
        yield db
    finally:
        db.close()
