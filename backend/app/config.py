from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlsplit


class Settings(BaseSettings):
    app_env: str = "development"
    demo_mode: bool = True
    allow_registration: bool = False
    database_url: str = "sqlite:///./vantage_iq.db"
    secret_key: str | None = None
    session_cookie_secure: bool | None = None
    trusted_hosts: str = ""
    database_ssl_ca: str | None = None
    session_cookie_name: str = Field(default="vantage_session", min_length=1, max_length=64, pattern="^[A-Za-z0-9_-]+$")
    session_ttl_hours: int = Field(default=12, ge=1, le=720)
    auth_action_token_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    upload_max_bytes: int = Field(default=5 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)
    cors_origins: str = "http://localhost:5173"
    public_app_url: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    smtp_starttls: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_deployment_settings(self):
        if "*" in self.allowed_origins:
            raise ValueError("Wildcard CORS origins are not allowed.")
        if not self.trusted_host_list or "*" in self.trusted_host_list:
            raise ValueError("Explicit trusted hosts are required; wildcard hosts are not allowed.")
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together.")
        if self.app_env.lower() in {"prod", "production"}:
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be false in production.")
            if not self.secret_key or len(self.secret_key.encode()) < 32:
                raise ValueError("SECRET_KEY must be configured with at least 32 bytes in production.")
            if self.session_cookie_secure is not True:
                raise ValueError("SESSION_COOKIE_SECURE=true is required in production.")
            if not self.allowed_origins:
                raise ValueError("At least one explicit CORS origin is required.")
            if not self.database_url.startswith("mysql+pymysql://"):
                raise ValueError("DATABASE_URL must use the MySQL PyMySQL driver in production.")
            if not self.database_ssl_ca or not Path(self.database_ssl_ca).is_absolute():
                raise ValueError("DATABASE_SSL_CA must point to an absolute path for verified MySQL TLS.")
            if not self.smtp_host or not self.smtp_from_address:
                raise ValueError("SMTP_HOST and SMTP_FROM_ADDRESS are required in production.")
            if not self.smtp_starttls:
                raise ValueError("SMTP_STARTTLS=true is required in production.")
            if not self.trusted_host_list:
                raise ValueError("TRUSTED_HOSTS must contain the application hostnames in production.")
            app_url = urlsplit(self.public_app_url)
            if app_url.scheme != "https" or not app_url.hostname or app_url.path not in {"", "/"} or app_url.query or app_url.fragment:
                raise ValueError("PUBLIC_APP_URL must be an HTTPS origin.")
            if not self.trusted_host_list:
                raise ValueError("TRUSTED_HOSTS must contain the application hostnames.")
            for origin in self.allowed_origins:
                parsed = urlsplit(origin)
                if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
                    raise ValueError("Production CORS origins must be HTTPS origins without a path.")
                if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
                    raise ValueError("Loopback origins are not allowed in production.")
        if self.session_cookie_secure is None:
            self.session_cookie_secure = self.app_env.lower() in {"prod", "production"}
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
        if hosts:
            return hosts
        return [] if self.app_env.lower() in {"prod", "production"} else ["localhost", "127.0.0.1", "testserver"]


settings = Settings()
