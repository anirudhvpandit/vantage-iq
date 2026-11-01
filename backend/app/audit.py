from sqlalchemy import event
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Alert,
    AuditEvent,
    Budget,
    Customer,
    Department,
    ExpenseTransaction,
    LoginSession,
    Organization,
    OrganizationMembership,
    Project,
    RevenueTransaction,
    User,
)

_AUDITED_TYPES = (
    Alert,
    Budget,
    Customer,
    Department,
    ExpenseTransaction,
    LoginSession,
    Organization,
    OrganizationMembership,
    Project,
    RevenueTransaction,
    User,
)


@event.listens_for(Session, "before_flush")
def collect_audited_changes(session: Session, flush_context, instances) -> None:
    pending = session.info.setdefault("audit_pending", [])
    for action, objects in (
        ("created", session.new),
        ("updated", session.dirty),
        ("deleted", session.deleted),
    ):
        for obj in objects:
            if not isinstance(obj, _AUDITED_TYPES):
                continue
            if action == "updated" and not session.is_modified(obj, include_collections=False):
                continue
            event_action = action
            if isinstance(obj, LoginSession):
                if event_action == "created":
                    event_action = "login"
                elif event_action == "updated" and inspect(obj).attrs.revoked_at.history.has_changes():
                    event_action = "logout"
                elif event_action == "updated" and inspect(obj).attrs.active_organization_id.history.has_changes():
                    event_action = "organization_switched"
            elif isinstance(obj, User) and event_action == "updated":
                state = inspect(obj)
                if state.attrs.email_verified.history.has_changes():
                    event_action = "email_verified"
                elif state.attrs.password_hash.history.has_changes():
                    event_action = "password_changed"
            pending.append((event_action, obj))


@event.listens_for(Session, "after_flush_postexec")
def persist_audit_events(session: Session, flush_context) -> None:
    pending = session.info.pop("audit_pending", [])
    for action, obj in pending:
        organization_id = getattr(obj, "organization_id", None)
        if isinstance(obj, Organization):
            organization_id = obj.id
        elif isinstance(obj, LoginSession):
            organization_id = obj.active_organization_id
        if organization_id is None:
            organization_id = session.info.get("audit_organization_id")
        actor_id = session.info.get("audit_actor_user_id")
        if actor_id is None and isinstance(obj, User) and action == "created":
            actor_id = obj.id
        organization_ids = [organization_id]
        if isinstance(obj, User) and action in {"email_verified", "password_changed"}:
            organization_ids = session.scalars(
                select(OrganizationMembership.organization_id).where(OrganizationMembership.user_id == obj.id)
            ).all() or [None]
        for event_organization_id in organization_ids:
            session.add(
                AuditEvent(
                    actor_user_id=actor_id,
                    organization_id=event_organization_id,
                    action=action,
                    entity_type=obj.__tablename__,
                    entity_id=getattr(obj, "id", None),
                    request_id=session.info.get("request_id"),
                )
            )
