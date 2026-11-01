from datetime import date
from decimal import Decimal
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    Alert,
    Budget,
    Customer,
    Department,
    ExpenseTransaction,
    Organization,
    OrganizationMembership,
    Project,
    RevenueTransaction,
    User,
)
from .security import TenantContext, get_authenticated_user, get_tenant_context, require_permission

router = APIRouter(prefix="/api/v1", tags=["business data"])
Model = TypeVar("Model")


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DepartmentInput(InputModel):
    name: str = Field(min_length=1, max_length=100)


class CustomerInput(InputModel):
    name: str = Field(min_length=1, max_length=160)
    segment: str = Field(min_length=1, max_length=80)
    status: str = Field(default="Active", min_length=1, max_length=24)
    account_owner: str = Field(min_length=1, max_length=100)


class ProjectInput(InputModel):
    customer_id: int
    department_id: int
    name: str = Field(min_length=1, max_length=160)
    manager: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=24)
    start_date: date
    planned_end_date: date
    actual_end_date: date | None = None
    budget: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    actual_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    planned_progress: int = Field(ge=0, le=100)
    actual_progress: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_project_dates(self):
        if self.planned_end_date < self.start_date:
            raise ValueError("planned_end_date must be on or after start_date.")
        return self


class BudgetInput(InputModel):
    department_id: int
    period_start: date
    revenue_target: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    expense_budget: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class RevenueInput(InputModel):
    customer_id: int
    department_id: int
    external_id: str = Field(min_length=1, max_length=120)
    transaction_date: date
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    description: str = Field(min_length=1, max_length=240)
    revenue_type: str = Field(default="recognized", min_length=1, max_length=24)


class ExpenseInput(InputModel):
    department_id: int
    transaction_date: date
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)


class DepartmentPatch(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class CustomerPatch(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    segment: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = Field(default=None, min_length=1, max_length=24)
    account_owner: str | None = Field(default=None, min_length=1, max_length=100)


class ProjectPatch(InputModel):
    customer_id: int | None = None
    department_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    manager: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=24)
    start_date: date | None = None
    planned_end_date: date | None = None
    actual_end_date: date | None = None
    budget: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    actual_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    planned_progress: int | None = Field(default=None, ge=0, le=100)
    actual_progress: int | None = Field(default=None, ge=0, le=100)


class BudgetPatch(InputModel):
    department_id: int | None = None
    period_start: date | None = None
    revenue_target: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    expense_budget: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class RevenuePatch(InputModel):
    customer_id: int | None = None
    department_id: int | None = None
    external_id: str | None = Field(default=None, min_length=1, max_length=120)
    transaction_date: date | None = None
    amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    description: str | None = Field(default=None, min_length=1, max_length=240)
    revenue_type: str | None = Field(default=None, min_length=1, max_length=24)


class ExpensePatch(InputModel):
    department_id: int | None = None
    transaction_date: date | None = None
    amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=240)


class OrganizationInput(InputModel):
    name: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")


class MemberInput(InputModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(pattern="^(owner|admin|analyst|viewer)$")


class MemberRoleInput(InputModel):
    role: str = Field(pattern="^(owner|admin|analyst|viewer)$")


def _records(db: Session, model: type[Model], organization_id: int, limit: int, offset: int):
    return db.scalars(
        select(model)
        .where(model.organization_id == organization_id)
        .order_by(model.id)
        .limit(limit)
        .offset(offset)
    ).all()


def _get(db: Session, model: type[Model], record_id: int, organization_id: int):
    record = db.scalar(
        select(model).where(model.id == record_id, model.organization_id == organization_id)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


def _ensure_related(db: Session, model, record_id: int, organization_id: int) -> None:
    if db.scalar(select(model.id).where(model.id == record_id, model.organization_id == organization_id)) is None:
        raise HTTPException(status_code=422, detail="Related record must belong to the active organization.")


def _persist(db: Session, record):
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="The change conflicts with an existing record.") from error


def _dump(record):
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def _patch(db: Session, model, record_id: int, organization_id: int, payload: BaseModel, related=None):
    record = _get(db, model, record_id, organization_id)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="At least one field must be provided.")
    if any(value is None and not (model is Project and field == "actual_end_date") for field, value in values.items()):
        raise HTTPException(status_code=422, detail="Null is only allowed for a project's actual_end_date.")
    for relation_field, related_model in (related or {}).items():
        if relation_field in values:
            _ensure_related(db, related_model, values[relation_field], organization_id)
    for field, value in values.items():
        setattr(record, field, value)
    return _persist(db, record)


def _delete(db: Session, model, record_id: int, organization_id: int) -> Response:
    record = _get(db, model, record_id, organization_id)
    db.delete(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Record is in use and cannot be deleted.") from error
    return Response(status_code=204)


@router.get("/organizations")
def organizations(user: User | None = Depends(get_authenticated_user), db: Session = Depends(get_db)):
    if user is None:
        organization = db.scalar(select(Organization).where(Organization.is_demo.is_(True)))
        return {"items": [{"id": organization.id, "name": organization.name, "currency": organization.currency, "role": "viewer"}]} if organization else {"items": []}
    rows = db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(Organization.id)
    ).all()
    return {"items": [{"id": membership.organization_id, "name": organization.name, "currency": organization.currency, "role": membership.role} for membership, organization in rows]}


def _require_path_org(context: TenantContext, organization_id: int) -> None:
    if context.organization.id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found.")


def _lock_organization(db: Session, organization_id: int) -> None:
    if db.scalar(select(Organization.id).where(Organization.id == organization_id).with_for_update()) is None:
        raise HTTPException(status_code=404, detail="Organization not found.")


def _lock_owner_memberships(db: Session, organization_id: int) -> list[int]:
    return db.scalars(
        select(OrganizationMembership.user_id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == "owner",
        )
        .with_for_update()
    ).all()


@router.get("/organizations/{organization_id}/members")
def list_members(
    organization_id: int,
    context: TenantContext = Depends(require_permission("manage_members")),
    db: Session = Depends(get_db),
):
    _require_path_org(context, organization_id)
    rows = db.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(User.email)
    ).all()
    return {"items": [{"user_id": member.user_id, "email": user.email, "role": member.role} for member, user in rows]}


@router.post("/organizations/{organization_id}/members", status_code=201)
def add_member(
    organization_id: int,
    payload: MemberInput,
    context: TenantContext = Depends(require_permission("manage_members")),
    db: Session = Depends(get_db),
):
    _require_path_org(context, organization_id)
    role = payload.role
    if context.role != "owner" and role in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only an owner can grant owner or admin roles.")
    email = payload.email.strip().casefold()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=404, detail="User account not found.")
    if db.scalar(select(OrganizationMembership.id).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == organization_id,
    )):
        raise HTTPException(status_code=409, detail="User is already a member of this organization.")
    member = OrganizationMembership(user_id=user.id, organization_id=organization_id, role=role)
    db.add(member)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member of this organization.") from error
    return {"user_id": user.id, "email": user.email, "role": role}


@router.delete("/organizations/{organization_id}/members/{user_id}", status_code=204)
def remove_member(
    organization_id: int,
    user_id: int,
    context: TenantContext = Depends(require_permission("manage_members")),
    db: Session = Depends(get_db),
):
    _require_path_org(context, organization_id)
    _lock_organization(db, organization_id)
    membership = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
    ).with_for_update())
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization member not found.")
    owner_ids = _lock_owner_memberships(db, organization_id)
    if context.role != "owner" and membership.role == "owner":
        raise HTTPException(status_code=403, detail="Only an owner can remove an owner.")
    if membership.role == "owner" and len(owner_ids) <= 1:
        raise HTTPException(status_code=409, detail="An organization must retain at least one owner.")
    db.delete(membership)
    db.commit()
    return Response(status_code=204)


@router.patch("/organizations/{organization_id}/members/{user_id}")
def update_member_role(
    organization_id: int,
    user_id: int,
    payload: MemberRoleInput,
    context: TenantContext = Depends(require_permission("manage_members")),
    db: Session = Depends(get_db),
):
    _require_path_org(context, organization_id)
    _lock_organization(db, organization_id)
    membership = db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
    ).with_for_update())
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization member not found.")
    owner_ids = _lock_owner_memberships(db, organization_id)
    if context.role != "owner" and (membership.role == "owner" or payload.role in {"owner", "admin"}):
        raise HTTPException(status_code=403, detail="Only an owner can change owner or admin roles.")
    if membership.role == "owner" and payload.role != "owner" and len(owner_ids) <= 1:
        raise HTTPException(status_code=409, detail="An organization must retain at least one owner.")
    membership.role = payload.role
    db.commit()
    user = db.get(User, user_id)
    return {"user_id": user_id, "email": user.email, "role": membership.role}


@router.post("/organizations", status_code=201)
def create_organization(
    payload: OrganizationInput,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
    _: TenantContext = Depends(require_permission("write")),
):
    if context.user is None:
        raise HTTPException(status_code=403, detail="Demo data is read-only.")
    organization = Organization(name=payload.name.strip(), currency=payload.currency.upper())
    if not organization.name:
        raise HTTPException(status_code=422, detail="Organization name is required.")
    db.add(organization)
    db.flush()
    db.add(OrganizationMembership(user_id=context.user.id, organization_id=organization.id, role="owner"))
    db.commit()
    return {"id": organization.id, "name": organization.name, "currency": organization.currency, "role": "owner"}


@router.get("/departments")
def list_departments(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, Department, context.organization.id, limit, offset)], "limit": limit, "offset": offset}


@router.get("/customers")
def list_customers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, Customer, context.organization.id, limit, offset)], "limit": limit, "offset": offset}


@router.post("/departments", status_code=201)
def create_department(payload: DepartmentInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_persist(db, Department(organization_id=context.organization.id, **payload.model_dump())))


@router.get("/departments/{record_id}")
def get_department(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, Department, record_id, context.organization.id))


@router.patch("/departments/{record_id}")
def update_department(record_id: int, payload: DepartmentPatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_patch(db, Department, record_id, context.organization.id, payload))


@router.delete("/departments/{record_id}", status_code=204)
def delete_department(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, Department, record_id, context.organization.id)


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_persist(db, Customer(organization_id=context.organization.id, **payload.model_dump())))


@router.get("/customers/{record_id}")
def get_customer(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, Customer, record_id, context.organization.id))


@router.patch("/customers/{record_id}")
def update_customer(record_id: int, payload: CustomerPatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_patch(db, Customer, record_id, context.organization.id, payload))


@router.delete("/customers/{record_id}", status_code=204)
def delete_customer(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, Customer, record_id, context.organization.id)


@router.post("/projects", status_code=201)
def create_project(payload: ProjectInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    _ensure_related(db, Customer, payload.customer_id, context.organization.id)
    _ensure_related(db, Department, payload.department_id, context.organization.id)
    return _dump(_persist(db, Project(organization_id=context.organization.id, **payload.model_dump())))


@router.get("/projects/{record_id}")
def get_project(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, Project, record_id, context.organization.id))


@router.get("/projects")
def list_projects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, Project, context.organization.id, limit, offset)], "limit": limit, "offset": offset}



@router.patch("/projects/{record_id}")
def update_project(record_id: int, payload: ProjectPatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    current = _get(db, Project, record_id, context.organization.id)
    values = payload.model_dump(exclude_unset=True)
    start_date = values.get("start_date", current.start_date)
    planned_end_date = values.get("planned_end_date", current.planned_end_date)
    if start_date is not None and planned_end_date is not None and planned_end_date < start_date:
        raise HTTPException(status_code=422, detail="planned_end_date must be on or after start_date.")
    return _dump(_patch(db, Project, record_id, context.organization.id, payload, {"customer_id": Customer, "department_id": Department}))


@router.delete("/projects/{record_id}", status_code=204)
def delete_project(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, Project, record_id, context.organization.id)


@router.get("/budgets")
def list_budgets(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, Budget, context.organization.id, limit, offset)], "limit": limit, "offset": offset}


@router.post("/budgets", status_code=201)
def create_budget(payload: BudgetInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    _ensure_related(db, Department, payload.department_id, context.organization.id)
    return _dump(_persist(db, Budget(organization_id=context.organization.id, **payload.model_dump())))


@router.get("/budgets/{record_id}")
def get_budget(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, Budget, record_id, context.organization.id))


@router.patch("/budgets/{record_id}")
def update_budget(record_id: int, payload: BudgetPatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_patch(db, Budget, record_id, context.organization.id, payload, {"department_id": Department}))


@router.delete("/budgets/{record_id}", status_code=204)
def delete_budget(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, Budget, record_id, context.organization.id)


@router.post("/revenue", status_code=201)
def create_revenue(payload: RevenueInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    _ensure_related(db, Customer, payload.customer_id, context.organization.id)
    _ensure_related(db, Department, payload.department_id, context.organization.id)
    values = payload.model_dump()
    values["currency"] = values["currency"].upper()
    if values["currency"] != context.organization.currency:
        raise HTTPException(status_code=422, detail="Currency must match the active organization.")
    return _dump(_persist(db, RevenueTransaction(organization_id=context.organization.id, **values)))


@router.get("/revenue/{record_id}")
def get_revenue(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, RevenueTransaction, record_id, context.organization.id))


@router.patch("/revenue/{record_id}")
def update_revenue(record_id: int, payload: RevenuePatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    values = payload.model_dump(exclude_unset=True)
    if values.get("customer_id") is not None:
        _ensure_related(db, Customer, values["customer_id"], context.organization.id)
    if values.get("department_id") is not None:
        _ensure_related(db, Department, values["department_id"], context.organization.id)
    if "currency" in values and values["currency"] is not None:
        values["currency"] = values["currency"].upper()
        if values["currency"] != context.organization.currency:
            raise HTTPException(status_code=422, detail="Currency must match the active organization.")
    return _dump(_patch(db, RevenueTransaction, record_id, context.organization.id, payload.model_copy(update=values), {"customer_id": Customer, "department_id": Department}))


@router.delete("/revenue/{record_id}", status_code=204)
def delete_revenue(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, RevenueTransaction, record_id, context.organization.id)


@router.get("/expenses")
def list_expenses(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, ExpenseTransaction, context.organization.id, limit, offset)], "limit": limit, "offset": offset}


@router.post("/expenses", status_code=201)
def create_expense(payload: ExpenseInput, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    _ensure_related(db, Department, payload.department_id, context.organization.id)
    return _dump(_persist(db, ExpenseTransaction(organization_id=context.organization.id, **payload.model_dump())))


@router.get("/expenses/{record_id}")
def get_expense(record_id: int, context: TenantContext = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return _dump(_get(db, ExpenseTransaction, record_id, context.organization.id))


@router.patch("/expenses/{record_id}")
def update_expense(record_id: int, payload: ExpensePatch, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    return _dump(_patch(db, ExpenseTransaction, record_id, context.organization.id, payload, {"department_id": Department}))


@router.delete("/expenses/{record_id}", status_code=204)
def delete_expense(record_id: int, context: TenantContext = Depends(require_permission("delete")), db: Session = Depends(get_db)):
    return _delete(db, ExpenseTransaction, record_id, context.organization.id)


@router.patch("/alerts/{record_id}/acknowledge")
def acknowledge_alert(record_id: int, context: TenantContext = Depends(require_permission("write")), db: Session = Depends(get_db)):
    record = _get(db, Alert, record_id, context.organization.id)
    record.acknowledged = True
    return _dump(_persist(db, record))


@router.get("/revenue")
def list_revenue(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: TenantContext = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    return {"items": [_dump(row) for row in _records(db, RevenueTransaction, context.organization.id, limit, offset)], "limit": limit, "offset": offset}
