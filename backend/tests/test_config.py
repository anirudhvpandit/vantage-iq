import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_requires_mysql_secret_secure_cookie_and_https_origin():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            demo_mode=False,
            database_url="sqlite:///./vantage_iq.db",
            secret_key="x" * 40,
            session_cookie_secure=True,
            cors_origins="https://app.example.com",
        )

    config = Settings(
        app_env="production",
        demo_mode=False,
        database_url="mysql+pymysql://user:pass@db.example.com/vantage",
        secret_key="x" * 40,
        session_cookie_secure=True,
        cors_origins="https://app.example.com",
        public_app_url="https://app.example.com",
        database_ssl_ca="/etc/ssl/certs/mysql-ca.pem",
        smtp_host="smtp.example.com",
        smtp_from_address="noreply@example.com",
        trusted_hosts="api.example.com",
    )
    assert config.session_cookie_secure is True
    assert config.trusted_host_list == ["api.example.com"]


def test_production_requires_verified_email_tls_and_trusted_host_configuration():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            demo_mode=False,
            database_url="mysql+pymysql://user:password@db.example.com/vantage",
            secret_key="x" * 40,
            session_cookie_secure=True,
            cors_origins="https://app.example.com",
            public_app_url="https://app.example.com",
            database_ssl_ca="/etc/ssl/certs/mysql-ca.pem",
        )


def test_wildcard_cors_is_rejected_outside_production_too():
    with pytest.raises(ValidationError):
        Settings(
            app_env="development",
            demo_mode=True,
            database_url="sqlite:///./vantage_iq.db",
            cors_origins="*",
        )
