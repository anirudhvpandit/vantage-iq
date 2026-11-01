import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .email_delivery import EmailDeliveryError, send_action_email
from .models import AuditEvent, EmailActionToken, LoginSession, Organization, OrganizationMembership, User
from .rate_limit import enforce_rate_limit

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
organization_router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
ROLE_PERMISSIONS = {
    "owner": {"read", "write", "delete", "manage_members"},
    "admin": {"read", "write", "delete", "manage_members"},
    "analyst": {"read", "write"},
    "viewer": {"read"},
}
_DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))
_logger = logging.getLogger(__name__)


class RegisterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=1, max_length=160)


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class EmailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)


class ActionTokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=128)


class PasswordResetPayload(ActionTokenPayload):
    password: str = Field(min_length=12, max_length=128)


@dataclass(frozen=True)
class TenantContext:
    user: User | None
    organization: Organization
    role: str
    session: LoginSession | None = None


def _email(value: str) -> str:
    email = value.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="A valid email address is required.")
    return email


def _digest(value: str) -> str:
    key = (settings.secret_key or "development-only-session-key").encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _session_response(db: Session, user: User, csrf_token: str, active_organization_id: int | None) -> dict:
    rows = db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(Organization.id)
    ).all()
    return {
        "user": {"id": user.id, "email": user.email, "email_verified": user.email_verified},
        "csrf_token": csrf_token,
        "memberships": [
            {
                "organization_id": membership.organization_id,
                "organization_name": organization.name,
                "role": membership.role,
                "is_demo": organization.is_demo,
            }
            for membership, organization in rows
        ],
        "active_organization_id": active_organization_id,
    }


def _set_session(response: Response, db: Session, user: User, active_organization_id: int | None = None) -> dict:
    memberships = db.scalars(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).all()
    if active_organization_id is None and len(memberships) == 1:
        active_organization_id = memberships[0].organization_id
    token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    record = LoginSession(
        user_id=user.id,
        token_hash=_digest(token),
        csrf_hash=_digest(csrf_token),
        active_organization_id=active_organization_id,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
    )
    db.info["audit_actor_user_id"] = user.id
    db.info["audit_organization_id"] = active_organization_id
    db.add(record)
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=bool(settings.session_cookie_secure),
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )
    response.set_cookie(
        "vantage_csrf",
        csrf_token,
        httponly=False,
        secure=bool(settings.session_cookie_secure),
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )
    return _session_response(db, user, csrf_token, active_organization_id)


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=bool(settings.session_cookie_secure),
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        "vantage_csrf",
        path="/",
        secure=bool(settings.session_cookie_secure),
        httponly=False,
        samesite="lax",
    )


def _get_login_session(request: Request, db: Session) -> tuple[LoginSession, User] | None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token or len(raw_token) > 256:
        return None
    row = db.execute(
        select(LoginSession, User)
        .join(User, User.id == LoginSession.user_id)
        .where(LoginSession.token_hash == _digest(raw_token))
    ).first()
    if row is None:
        return None
    login_session, user = row
    if (
        login_session.revoked_at is not None
        or login_session.expires_at <= datetime.utcnow()
        or not user.is_active
        or not user.email_verified
    ):
        return None
    return login_session, user


def get_authenticated_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    if settings.demo_mode:
        return None
    authenticated = _get_login_session(request, db)
    if authenticated is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return authenticated[1]


def get_tenant_context(
    request: Request,
    db: Session = Depends(get_db),
    organization_header_id: int | None = Header(default=None, alias="X-Organization-ID"),
) -> TenantContext:
    if settings.demo_mode:
        organization = db.scalar(select(Organization).where(Organization.is_demo.is_(True)))
        if organization is None:
            raise HTTPException(status_code=503, detail="Demo dataset is not initialized.")
        return TenantContext(None, organization, "viewer")

    authenticated = _get_login_session(request, db)
    if authenticated is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    login_session, user = authenticated
    db.info["audit_actor_user_id"] = user.id
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not csrf_token or not hmac.compare_digest(_digest(csrf_token), login_session.csrf_hash):
            raise HTTPException(status_code=403, detail="A valid CSRF token is required.")
    memberships = db.scalars(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).all()
    if organization_header_id is None:
        active_id = login_session.active_organization_id
        membership = next((item for item in memberships if item.organization_id == active_id), None)
        if membership is not None:
            pass
        elif len(memberships) == 1:
            membership = memberships[0]
        else:
            raise HTTPException(status_code=400, detail="X-Organization-ID is required when the account has multiple organizations.")
    else:
        membership = next((item for item in memberships if item.organization_id == organization_header_id), None)
        if membership is None:
            raise HTTPException(status_code=404, detail="Organization not found.")
    organization = db.get(Organization, membership.organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    db.info["audit_organization_id"] = organization.id
    return TenantContext(user, organization, membership.role, login_session)


def require_permission(permission: str):
    def dependency(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if settings.demo_mode and permission != "read":
            raise HTTPException(status_code=403, detail="Demo data is read-only.")
        if permission not in ROLE_PERMISSIONS.get(context.role, set()):
            raise HTTPException(status_code=403, detail="Insufficient organization permissions.")
        return context

    return dependency


def _issue_action_token(db: Session, user: User, purpose: str) -> str:
    now = datetime.utcnow()
    db.execute(
        update(EmailActionToken)
        .where(
            EmailActionToken.user_id == user.id,
            EmailActionToken.purpose == purpose,
            EmailActionToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    token = secrets.token_urlsafe(32)
    db.add(
        EmailActionToken(
            user_id=user.id,
            token_hash=_digest(token),
            purpose=purpose,
            expires_at=now + timedelta(minutes=settings.auth_action_token_ttl_minutes),
        )
    )
    db.commit()
    return token


def _send_action_email(user: User, purpose: str, token: str) -> None:
    route = "verify-email" if purpose == "verify_email" else "reset-password"
    action = "verify your email address" if purpose == "verify_email" else "reset your password"
    action_url = f"{settings.public_app_url.rstrip('/')}/{route}?{urlencode({'token': token})}"
    subject = "Verify your Vantage IQ email" if purpose == "verify_email" else "Reset your Vantage IQ password"
    try:
        send_action_email(user.email, subject, action_url, action)
    except EmailDeliveryError as error:
        _logger.error("Account action email delivery failed for purpose %s: %s", purpose, error)


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register(payload: RegisterPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    if settings.demo_mode or not settings.allow_registration:
        raise HTTPException(status_code=404, detail="Not found.")
    email = _email(payload.email)
    enforce_rate_limit(request, db, scope="register_ip", identity="all", limit=10, window_seconds=3600)
    enforce_rate_limit(request, db, scope="register_email", identity=email, limit=3, window_seconds=3600)
    organization_name = payload.organization_name.strip()
    if not organization_name:
        raise HTTPException(status_code=422, detail="Organization name is required.")
    try:
        organization = Organization(name=organization_name, currency="USD")
        db.add(organization)
        db.flush()
        db.info["audit_organization_id"] = organization.id
        user = User(email=email, password_hash=password_hasher.hash(payload.password), email_verified=False)
        db.add(user)
        db.flush()
        db.info["audit_actor_user_id"] = user.id
        db.add(OrganizationMembership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        return {"status": "verification_required"}
    token = _issue_action_token(db, user, "verify_email")
    _send_action_email(user, "verify_email", token)
    return {"status": "verification_required"}


@router.post("/verify-email")
def verify_email(payload: ActionTokenPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce_rate_limit(request, db, scope="verify_email_ip", identity="all", limit=20, window_seconds=3600)
    action_token = db.scalar(
        select(EmailActionToken).where(
            EmailActionToken.token_hash == _digest(payload.token),
            EmailActionToken.purpose == "verify_email",
        ).with_for_update()
    )
    now = datetime.utcnow()
    if action_token is None or action_token.consumed_at is not None or action_token.expires_at <= now:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired.")
    user = db.get(User, action_token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="This verification link is invalid or expired.")
    action_token.consumed_at = now
    user.email_verified = True
    db.info["audit_actor_user_id"] = user.id
    db.commit()
    return {"status": "email_verified"}


@router.post("/verification/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(payload: EmailPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    email = _email(payload.email)
    enforce_rate_limit(request, db, scope="verification_resend_ip", identity="all", limit=20, window_seconds=3600)
    enforce_rate_limit(request, db, scope="verification_resend_email", identity=email, limit=4, window_seconds=3600)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and not user.email_verified:
        token = _issue_action_token(db, user, "verify_email")
        _send_action_email(user, "verify_email", token)
    return {"status": "request_received"}


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: EmailPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    email = _email(payload.email)
    enforce_rate_limit(request, db, scope="password_reset_ip", identity="all", limit=20, window_seconds=3600)
    enforce_rate_limit(request, db, scope="password_reset_email", identity=email, limit=4, window_seconds=3600)
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.is_active and user.email_verified:
        token = _issue_action_token(db, user, "password_reset")
        _send_action_email(user, "password_reset", token)
    return {"status": "request_received"}


@router.post("/password-reset/complete")
def complete_password_reset(payload: PasswordResetPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce_rate_limit(request, db, scope="password_reset_complete_ip", identity="all", limit=20, window_seconds=3600)
    action_token = db.scalar(
        select(EmailActionToken).where(
            EmailActionToken.token_hash == _digest(payload.token),
            EmailActionToken.purpose == "password_reset",
        ).with_for_update()
    )
    now = datetime.utcnow()
    if action_token is None or action_token.consumed_at is not None or action_token.expires_at <= now:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    user = db.get(User, action_token.user_id)
    if user is None or not user.is_active or not user.email_verified:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    action_token.consumed_at = now
    user.password_hash = password_hasher.hash(payload.password)
    db.info["audit_actor_user_id"] = user.id
    db.execute(
        update(LoginSession)
        .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    return {"status": "password_reset"}


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    if settings.demo_mode:
        raise HTTPException(status_code=404, detail="Not found.")
    email = _email(payload.email)
    enforce_rate_limit(request, db, scope="login_ip", identity="all", limit=30, window_seconds=900)
    enforce_rate_limit(request, db, scope="login_email", identity=email, limit=10, window_seconds=900)
    user = db.scalar(select(User).where(User.email == email))
    password_hash = user.password_hash if user else _DUMMY_HASH
    try:
        password_hasher.verify(password_hash, payload.password)
        valid = user is not None
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if not valid or user is None or not user.is_active or not user.email_verified:
        db.add(AuditEvent(action="login_failed", entity_type="authentication", request_id=db.info.get("request_id")))
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _set_session(response, db, user)


@router.get("/me")
def who_am_i(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_authenticated_user),
) -> dict:
    if settings.demo_mode:
        organization = db.scalar(select(Organization).where(Organization.is_demo.is_(True)))
        return {
            "user": None,
            "memberships": [{
                "organization_id": organization.id,
                "organization_name": organization.name,
                "role": "viewer",
                "is_demo": True,
            }] if organization else [],
            "active_organization_id": organization.id if organization else None,
        }
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    memberships = db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user.id)
    ).all()
    authenticated = _get_login_session(request, db)
    active_id = authenticated[0].active_organization_id if authenticated else None
    header_id = request.headers.get("X-Organization-ID")
    if header_id is not None:
        try:
            requested_id = int(header_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="X-Organization-ID must be an integer.") from error
        if not any(member.organization_id == requested_id for member, _ in memberships):
            raise HTTPException(status_code=404, detail="Organization not found.")
        active_id = requested_id
    elif not any(member.organization_id == active_id for member, _ in memberships) and len(memberships) == 1:
        active_id = memberships[0][0].organization_id
    return {
        "user": {"id": user.id, "email": user.email, "email_verified": user.email_verified},
        "memberships": [
            {
                "organization_id": member.organization_id,
                "organization_name": organization.name,
                "role": member.role,
                "is_demo": organization.is_demo,
            }
            for member, organization in memberships
        ],
        "active_organization_id": active_id,
    }


@organization_router.post("/{organization_id}/switch")
def switch_organization(
    organization_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    if settings.demo_mode:
        raise HTTPException(status_code=404, detail="Not found.")
    authenticated = _get_login_session(request, db)
    if authenticated is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    login_session, user = authenticated
    csrf_token = request.headers.get("X-CSRF-Token", "")
    if not csrf_token or not hmac.compare_digest(_digest(csrf_token), login_session.csrf_hash):
        raise HTTPException(status_code=403, detail="A valid CSRF token is required.")
    enforce_rate_limit(request, db, scope="organization_switch", identity=str(user.id), limit=30, window_seconds=300)
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    login_session.active_organization_id = organization_id
    db.info["audit_actor_user_id"] = user.id
    db.info["audit_organization_id"] = organization_id
    db.commit()
    organization = db.get(Organization, organization_id)
    return {
        "active_organization_id": organization_id,
        "organization": {"id": organization.id, "name": organization.name},
        "role": membership.role,
    }


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    if settings.demo_mode:
        raise HTTPException(status_code=404, detail="Not found.")
    authenticated = _get_login_session(request, db)
    if authenticated is not None:
        login_session, user = authenticated
        csrf_token = request.headers.get("X-CSRF-Token", "")
        if not csrf_token or not hmac.compare_digest(_digest(csrf_token), login_session.csrf_hash):
            raise HTTPException(status_code=403, detail="A valid CSRF token is required.")
        login_session.revoked_at = datetime.utcnow()
        db.info["audit_actor_user_id"] = user.id
        db.info["audit_organization_id"] = login_session.active_organization_id
        db.commit()
    _clear_session_cookie(response)
    return {"status": "logged_out"}
