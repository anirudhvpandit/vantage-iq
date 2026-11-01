import csv
import io
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
from xml.etree.ElementTree import ParseError
from xml.sax.saxutils import escape
from zipfile import BadZipFile

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import desc, extract, func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .config import settings
from . import audit as _audit
from .calculations import budget_achievement, operating_margin, percent_change
from .database import get_db
from .models import (
    Alert,
    AuditEvent,
    Budget,
    Customer,
    Department,
    ExpenseTransaction,
    Organization,
    Project,
    RevenueTransaction,
    User,
)
from .seed import seed_demo_data
from .security import TenantContext, get_tenant_context, organization_router, router as auth_router
from .crud import router as crud_router

app = FastAPI(title="Vantage IQ API", version="1.0.0", description="Vantage IQ analytics and business data API.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Organization-ID"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)
if settings.app_env.lower() in {"prod", "production"}:
    app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
MAX_IMPORT_ROWS = 10_000
DEMO_DATA_START = date(2024, 11, 1)
DEMO_DATA_END = date(2026, 10, 31)
EXPECTED_MIGRATION_REVISION = ScriptDirectory.from_config(
    AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
).get_current_head()


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.on_event("startup")
def initialize_demo_data() -> None:
    if settings.demo_mode:
        from .database import SessionLocal

        with SessionLocal() as db:
            seed_demo_data(db)


def period_bounds(start_date: date | None, end_date: date | None) -> tuple[date, date, date, date]:
    latest = DEMO_DATA_END if settings.demo_mode else date.today()
    earliest = DEMO_DATA_START if settings.demo_mode else date(1970, 1, 1)
    end = end_date or latest
    default_start_year = end.year - 1 + (1 if end.month == 12 else 0)
    default_start_month = end.month % 12 + 1
    start = start_date or date(default_start_year, default_start_month, 1)
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if start < earliest:
        raise HTTPException(status_code=422, detail=f"Records begin on {earliest.isoformat()}.")
    if settings.demo_mode and end > DEMO_DATA_END:
        raise HTTPException(status_code=422, detail=f"Demo records end on {DEMO_DATA_END.isoformat()}.")
    duration = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    return start, end, previous_start, previous_end


def sum_revenue(db: Session, organization_id: int, start: date, end: date) -> Decimal:
    result = db.scalar(
        select(func.coalesce(func.sum(RevenueTransaction.amount), 0)).where(
            RevenueTransaction.organization_id == organization_id,
            RevenueTransaction.transaction_date.between(start, end),
            RevenueTransaction.revenue_type == "recognized",
        )
    )
    return Decimal(result or 0)


def sum_expenses(db: Session, organization_id: int, start: date, end: date) -> Decimal:
    result = db.scalar(
        select(func.coalesce(func.sum(ExpenseTransaction.amount), 0)).where(
            ExpenseTransaction.organization_id == organization_id,
            ExpenseTransaction.transaction_date.between(start, end),
        )
    )
    return Decimal(result or 0)


def decimal_value(value: Decimal | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def change_value(current: Decimal, previous: Decimal | None) -> float | None:
    return decimal_value(percent_change(current, previous)) if previous is not None else None


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo" if settings.demo_mode else "production"}


@app.get("/api/v1/ready")
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        revisions = db.scalars(text("SELECT version_num FROM alembic_version")).all()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable", "migration": "unavailable"},
        )
    if revisions != [EXPECTED_MIGRATION_REVISION]:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "ok", "migration": "not_at_head"},
        )
    return {"status": "ready", "database": "ok", "migration": EXPECTED_MIGRATION_REVISION}


@app.get("/api/v1/audit-events")
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100_000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    if context.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Insufficient organization permissions.")
    rows = db.execute(
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.organization_id == context.organization.id)
        .order_by(desc(AuditEvent.created_at), desc(AuditEvent.id))
        .offset(offset)
        .limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    return {
        "items": [
            {
                "id": event.id,
                "actor_user_id": event.actor_user_id,
                "actor_email": actor_email,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "request_id": event.request_id,
                "created_at": event.created_at.isoformat(),
            }
            for event, actor_email in rows[:limit]
        ],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@app.get("/api/v1/config")
def public_config() -> dict:
    return {
        "upload_max_bytes": settings.upload_max_bytes,
        "upload_max_rows": MAX_IMPORT_ROWS,
        "demo_data_start": DEMO_DATA_START.isoformat(),
        "demo_data_end": DEMO_DATA_END.isoformat(),
        "registration_enabled": settings.allow_registration and not settings.demo_mode,
        "roles": {
            "owner": ["read", "write", "delete", "manage_members"],
            "admin": ["read", "write", "delete", "manage_members"],
            "analyst": ["read", "write"],
            "viewer": ["read"],
        },
    }


def build_overview(
    db: Session,
    organization: Organization,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    start, end, prior_start, prior_end = period_bounds(start_date, end_date)
    revenue = sum_revenue(db, organization.id, start, end)
    costs = sum_expenses(db, organization.id, start, end)
    comparison_available = prior_start >= (DEMO_DATA_START if organization.is_demo else date(1970, 1, 1))
    previous_revenue = sum_revenue(db, organization.id, prior_start, prior_end) if comparison_available else None
    previous_costs = sum_expenses(db, organization.id, prior_start, prior_end) if comparison_available else None
    profit = revenue - costs
    previous_profit = previous_revenue - previous_costs if previous_revenue is not None and previous_costs is not None else None
    margin = operating_margin(revenue, costs)
    previous_margin = operating_margin(previous_revenue, previous_costs) if previous_revenue is not None and previous_costs is not None else None

    monthly_revenue = db.execute(
        select(
            extract("year", RevenueTransaction.transaction_date).label("year"),
            extract("month", RevenueTransaction.transaction_date).label("month"),
            func.sum(RevenueTransaction.amount).label("amount"),
        )
        .where(
            RevenueTransaction.organization_id == organization.id,
            RevenueTransaction.transaction_date.between(start, end),
            RevenueTransaction.revenue_type == "recognized",
        )
        .group_by("year", "month")
        .order_by("year", "month")
    ).all()
    monthly_costs = db.execute(
        select(
            extract("year", ExpenseTransaction.transaction_date).label("year"),
            extract("month", ExpenseTransaction.transaction_date).label("month"),
            func.sum(ExpenseTransaction.amount).label("amount"),
        )
        .where(
            ExpenseTransaction.organization_id == organization.id,
            ExpenseTransaction.transaction_date.between(start, end),
        )
        .group_by("year", "month")
        .order_by("year", "month")
    ).all()
    revenue_by_month = {(int(row.year), int(row.month)): float(row.amount) for row in monthly_revenue}
    costs_by_month = {(int(row.year), int(row.month)): float(row.amount) for row in monthly_costs}
    labels = []
    revenue_series = []
    cost_series = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        key = (cursor.year, cursor.month)
        labels.append(cursor.strftime("%b %y"))
        revenue_series.append(round(revenue_by_month.get(key, 0), 2))
        cost_series.append(round(costs_by_month.get(key, 0), 2))
        cursor = date(cursor.year + (cursor.month // 12), cursor.month % 12 + 1, 1)

    department_rows = db.execute(
        select(Department.name, func.sum(RevenueTransaction.amount))
        .join(RevenueTransaction, RevenueTransaction.department_id == Department.id)
        .where(
            Department.organization_id == organization.id,
            RevenueTransaction.organization_id == organization.id,
            RevenueTransaction.transaction_date.between(start, end),
            RevenueTransaction.revenue_type == "recognized",
        )
        .group_by(Department.name)
        .order_by(func.sum(RevenueTransaction.amount).desc())
    ).all()
    expense_rows = db.execute(
        select(ExpenseTransaction.category, func.sum(ExpenseTransaction.amount))
        .where(
            ExpenseTransaction.organization_id == organization.id,
            ExpenseTransaction.transaction_date.between(start, end),
        )
        .group_by(ExpenseTransaction.category)
        .order_by(func.sum(ExpenseTransaction.amount).desc())
    ).all()
    targets = Decimal("0")
    budget_month = date(start.year, start.month, 1)
    while budget_month <= end:
        next_month = date(budget_month.year + budget_month.month // 12, budget_month.month % 12 + 1, 1)
        month_end = next_month - timedelta(days=1)
        overlap_start = max(start, budget_month)
        overlap_end = min(end, month_end)
        month_target = db.scalar(
            select(func.coalesce(func.sum(Budget.revenue_target), 0)).where(
                Budget.organization_id == organization.id,
                Budget.period_start == budget_month,
            )
        )
        if month_target and overlap_start <= overlap_end:
            month_days = Decimal((month_end - budget_month).days + 1)
            overlap_days = Decimal((overlap_end - overlap_start).days + 1)
            targets += Decimal(month_target) * overlap_days / month_days
        budget_month = next_month
    project_rows = db.scalars(select(Project).where(Project.organization_id == organization.id)).all()
    completed = [project for project in project_rows if project.status == "Completed" and project.actual_end_date]
    on_time = (
        sum(project.actual_end_date <= project.planned_end_date for project in completed) / len(completed) * 100
        if completed
        else None
    )
    customer_count = db.scalar(
        select(func.count(Customer.id)).where(Customer.organization_id == organization.id)
    ) or 0
    recent_customers = db.scalar(
        select(func.count(func.distinct(RevenueTransaction.customer_id))).where(
            RevenueTransaction.organization_id == organization.id,
            RevenueTransaction.transaction_date.between(start, end),
            RevenueTransaction.revenue_type == "recognized",
        )
    ) or 0
    customer_activity_percent = (recent_customers / customer_count * 100) if customer_count else None
    return {
        "organization": {"name": organization.name, "currency": organization.currency, "synthetic_data": organization.is_demo},
        "period": {"start": start.isoformat(), "end": end.isoformat(), "comparison_start": prior_start.isoformat(), "comparison_end": prior_end.isoformat(), "comparison_available": comparison_available},
        "metrics": {
            "revenue": {"value": decimal_value(revenue), "change_percent": change_value(revenue, previous_revenue), "previous": decimal_value(previous_revenue)},
            "operating_costs": {"value": decimal_value(costs), "change_percent": change_value(costs, previous_costs), "previous": decimal_value(previous_costs)},
            "operating_profit": {"value": decimal_value(profit), "change_percent": change_value(profit, previous_profit), "previous": decimal_value(previous_profit)},
            "operating_margin": {"value": decimal_value(margin), "change_points": decimal_value(margin - previous_margin) if margin is not None and previous_margin is not None else None},
            "budget_achievement": {"value": decimal_value(budget_achievement(revenue, targets))},
            "on_time_delivery": {"value": round(on_time, 1) if on_time is not None else None, "eligible_completed_projects": len(completed)},
            "customer_activity": {"value": round(customer_activity_percent, 1) if customer_activity_percent is not None else None, "definition": "Distinct customers with recognized revenue in period divided by organization customer count; not a cohort retention measure."},
        },
        "trend": {"labels": labels, "revenue": revenue_series, "operating_costs": cost_series},
        "revenue_by_department": [{"name": name, "value": round(float(value), 2)} for name, value in department_rows],
        "cost_by_category": [{"name": name, "value": round(float(value), 2)} for name, value in expense_rows],
        "freshness": "Synthetic demo snapshot through 2026-10-31" if organization.is_demo else "Organization records",
    }


@app.get("/api/v1/overview")
def overview(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    return build_overview(db, context.organization, start_date, end_date)


@app.get("/api/v1/financial")
def financial(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    overview_data = build_overview(db, context.organization, start_date, end_date)
    return {
        "period": overview_data["period"],
        "currency": overview_data["organization"]["currency"],
        "metrics": overview_data["metrics"],
        "cost_by_category": overview_data["cost_by_category"],
        "limitations": [
            "Operating profit is recognized revenue minus recorded operating expenses.",
            "It is not net profit or EBITDA; non-operating items, taxes, interest, depreciation, and amortization are not modeled.",
            "Company-wide expenses are not allocated to departments.",
        ],
    }


@app.get("/api/v1/revenue/analytics")
def revenue(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    organization = context.organization
    start, end, _, _ = period_bounds(start_date, end_date)
    rows = db.execute(
        select(Customer.name, Customer.segment, func.sum(RevenueTransaction.amount).label("revenue"))
        .join(RevenueTransaction, RevenueTransaction.customer_id == Customer.id)
        .where(
            Customer.organization_id == organization.id,
            RevenueTransaction.organization_id == organization.id,
            RevenueTransaction.transaction_date.between(start, end),
            RevenueTransaction.revenue_type == "recognized",
        )
        .group_by(Customer.id, Customer.name, Customer.segment)
        .order_by(func.sum(RevenueTransaction.amount).desc())
        .limit(limit)
        .offset(offset)
    ).all()
    opportunities = [
        {"stage": "Qualified", "count": 8, "pipeline_value": 480000, "synthetic_example": True},
        {"stage": "Proposal", "count": 5, "pipeline_value": 395000, "synthetic_example": True},
        {"stage": "Negotiation", "count": 3, "pipeline_value": 280000, "synthetic_example": True},
    ] if organization.is_demo else []
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "recognized_revenue_by_customer": [
            {"customer": name, "segment": segment, "value": round(float(amount), 2)} for name, segment, amount in rows
        ],
        "pipeline": opportunities,
        "pipeline_note": (
            "Pipeline stages are fixed synthetic examples and are not included in recognized revenue."
            if organization.is_demo
            else "No opportunity pipeline is configured; only recognized revenue transactions are shown."
        ),
    }


@app.get("/api/v1/projects/health")
def projects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    organization = context.organization
    records = db.scalars(
        select(Project)
        .join(Customer, Customer.id == Project.customer_id)
        .join(Department, Department.id == Project.department_id)
        .where(
            Project.organization_id == organization.id,
            Customer.organization_id == organization.id,
            Department.organization_id == organization.id,
        )
        .order_by(Project.planned_end_date)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "customer_id": item.customer_id,
                "department_id": item.department_id,
                "name": item.name,
                "customer": item.customer.name,
                "department": item.department.name,
                "manager": item.manager,
                "status": item.status,
                "planned_end_date": item.planned_end_date.isoformat(),
                "start_date": item.start_date.isoformat(),
                "actual_end_date": item.actual_end_date.isoformat() if item.actual_end_date else None,
                "budget": float(item.budget),
                "actual_cost": float(item.actual_cost),
                "planned_progress": item.planned_progress,
                "actual_progress": item.actual_progress,
                "budget_variance": round(float(item.actual_cost - item.budget), 2),
            }
            for item in records
        ],
        "limit": limit,
        "offset": offset,
        "on_time_definition": "Completed projects delivered on or before planned end date divided by completed projects with an actual end date.",
    }


@app.get("/api/v1/customers/analytics")
def customers(
    search: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    organization = context.organization
    conditions = [Customer.organization_id == organization.id]
    if search.strip():
        conditions.append(Customer.name.ilike(f"%{search.strip()}%"))
    results = db.execute(
        select(
            Customer,
            func.coalesce(func.sum(RevenueTransaction.amount), 0).label("total"),
            func.max(RevenueTransaction.transaction_date).label("last_active"),
        )
        .outerjoin(
            RevenueTransaction,
            (RevenueTransaction.customer_id == Customer.id)
            & (RevenueTransaction.organization_id == organization.id)
            & (RevenueTransaction.revenue_type == "recognized"),
        )
        .where(*conditions)
        .group_by(Customer.id)
        .order_by(Customer.name)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        {
            "id": customer.id,
            "name": customer.name,
            "segment": customer.segment,
            "status": customer.status,
            "account_owner": customer.account_owner,
            "recognized_revenue": round(float(total or 0), 2),
            "last_revenue_date": last_active.isoformat() if last_active else None,
        }
        for customer, total, last_active in results
    ]
    return {"items": items, "synthetic_data": organization.is_demo, "limit": limit, "offset": offset}


@app.get("/api/v1/alerts")
def alerts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    organization = context.organization
    records = db.scalars(
        select(Alert)
        .where(Alert.organization_id == organization.id)
        .order_by(Alert.detected_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "severity": item.severity,
                "explanation": item.explanation,
                "suggested_action": item.suggested_action,
                "detected_at": item.detected_at.isoformat(),
                "acknowledged": item.acknowledged,
            }
            for item in records
        ],
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/v1/imports/revenue/template.csv")
def revenue_import_template() -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["external_id", "date", "customer", "department", "amount", "currency", "description"])
    writer.writerow(["replace-with-unique-id", "2026-10-15", "Asteron Manufacturing", "Field Services", "12500.00", "USD", "Example recognized revenue"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vantage-iq-revenue-import-template.csv"'},
    )


@app.get("/api/v1/imports/revenue/template.xlsx")
def revenue_import_xlsx_template() -> StreamingResponse:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Revenue import"
    headers = ["external_id", "date", "customer", "department", "amount", "currency", "description"]
    sheet.append(headers)
    sheet.append(["replace-with-unique-id", "2026-10-15", "Asteron Manufacturing", "Field Services", "12500.00", "USD", "Example recognized revenue"])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="27466B")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:G{sheet.max_row}"
    for column, width in zip("ABCDEFG", [26, 15, 28, 24, 16, 14, 38]):
        sheet.column_dimensions[column].width = width
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="vantage-iq-revenue-import-template.xlsx"'},
    )


def safe_spreadsheet_text(value: str) -> str:
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


@app.get("/api/v1/reports/executive.csv")
def executive_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    data = build_overview(db, context.organization, start_date, end_date)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value", "Unit", "Reporting period"])
    period = data["period"]
    rows = [
        ("Recognized revenue", data["metrics"]["revenue"]["value"], data["organization"]["currency"]),
        ("Operating costs", data["metrics"]["operating_costs"]["value"], data["organization"]["currency"]),
        ("Operating profit", data["metrics"]["operating_profit"]["value"], data["organization"]["currency"]),
        ("Operating margin", data["metrics"]["operating_margin"]["value"], "%"),
        ("Revenue target achievement", data["metrics"]["budget_achievement"]["value"], "%"),
    ]
    for name, value, unit in rows:
        writer.writerow([safe_spreadsheet_text(name), value if value is not None else "Not available", unit, f"{period['start']} to {period['end']}"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vantage-iq-executive-report.csv"'},
    )


@app.get("/api/v1/reports/executive.pdf")
def executive_report_pdf(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    data = build_overview(db, context.organization, start_date, end_date)
    period = data["period"]
    metrics = data["metrics"]
    rows = [
        ["Executive metric", "Value", "Unit"],
        ["Recognized revenue", metrics["revenue"]["value"] if metrics["revenue"]["value"] is not None else "Not available", data["organization"]["currency"]],
        ["Operating costs", metrics["operating_costs"]["value"] if metrics["operating_costs"]["value"] is not None else "Not available", data["organization"]["currency"]],
        ["Operating profit", metrics["operating_profit"]["value"] if metrics["operating_profit"]["value"] is not None else "Not available", data["organization"]["currency"]],
        ["Operating margin", metrics["operating_margin"]["value"] if metrics["operating_margin"]["value"] is not None else "Not available", "%"],
        ["Revenue target achievement", metrics["budget_achievement"]["value"] if metrics["budget_achievement"]["value"] is not None else "Not available", "%"],
    ]
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=letter, title="Vantage IQ Executive Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Vantage IQ Executive Report", styles["Title"]),
        Paragraph(
            f"{escape(context.organization.name)} - {period['start']} to {period['end']}",
            styles["Normal"],
        ),
        Spacer(1, 18),
    ]
    table = Table(rows, colWidths=[270, 150, 70], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27466B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 12), Paragraph(
        "Operating profit is recognized revenue less recorded operating expenses; it is not net profit or EBITDA.",
        styles["BodyText"],
    )])
    document.build(story)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="vantage-iq-executive-report.pdf"'},
    )


def read_import_rows(content: bytes, suffix: str) -> list[list[object]]:
    def collect_rows(source) -> list[list[object]]:
        collected = []
        for row in source:
            if len(collected) >= MAX_IMPORT_ROWS + 1:
                raise HTTPException(status_code=413, detail=f"Imports are limited to {MAX_IMPORT_ROWS:,} data rows.")
            collected.append(list(row))
        return collected

    if suffix == ".csv":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded.") from error
        try:
            return collect_rows(csv.reader(io.StringIO(text), strict=True))
        except csv.Error as error:
            raise HTTPException(status_code=422, detail="CSV structure is invalid.") from error
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            return collect_rows(workbook.active.iter_rows(values_only=True))
        finally:
            workbook.close()
    except (BadZipFile, InvalidFileException, OSError, KeyError, ValueError, ParseError, EOFError, IndexError) as error:
        raise HTTPException(status_code=422, detail="Could not read the XLSX workbook.") from error


def validate_revenue_import(content: bytes, filename: str, db: Session, organization_id: int) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=415, detail="Only CSV and XLSX files are supported.")
    rows = read_import_rows(content, suffix)
    if not rows or not rows[0]:
        raise HTTPException(status_code=422, detail="The file must include a header row.")
    headers = [str(value or "").strip().lower() for value in rows[0]]
    if len(headers) > 50:
        raise HTTPException(status_code=422, detail="The file must have no more than 50 columns.")
    if len(headers) != len(set(headers)):
        raise HTTPException(status_code=422, detail="Column names must be unique.")
    required = {"external_id", "date", "customer", "department", "amount", "currency", "description"}
    missing = sorted(required - set(headers))
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing required columns: {', '.join(missing)}")
    organization_currency = db.scalar(
        select(Organization.currency).where(Organization.id == organization_id)
    )
    positions = {header: index for index, header in enumerate(headers)}
    seen: set[str] = set()
    errors = []
    valid_rows = []
    supplied_ids = {
        str(row[positions["external_id"]] or "").strip()
        for row in rows[1:]
        if positions["external_id"] < len(row) and str(row[positions["external_id"]] or "").strip()
    }
    existing_ids: set[str] = set()
    supplied_id_list = list(supplied_ids)
    for offset in range(0, len(supplied_id_list), 500):
        existing_ids.update(
            db.scalars(
                select(RevenueTransaction.external_id).where(
                    RevenueTransaction.organization_id == organization_id,
                    RevenueTransaction.external_id.in_(supplied_id_list[offset : offset + 500]),
                )
            ).all()
        )
    customer_by_name = {
        customer.name: customer
        for customer in db.scalars(select(Customer).where(Customer.organization_id == organization_id)).all()
    }
    department_by_name = {
        department.name: department
        for department in db.scalars(select(Department).where(Department.organization_id == organization_id)).all()
    }
    for row_number, row in enumerate(rows[1:], start=2):
        values = {key: (row[index] if index < len(row) else None) for key, index in positions.items()}
        row_errors = []
        external_id = str(values["external_id"] or "").strip()
        customer_name = str(values["customer"] or "").strip()
        department_name = str(values["department"] or "").strip()
        if not external_id:
            row_errors.append("external_id is required")
        elif len(external_id) > 120:
            row_errors.append("external_id cannot exceed 120 characters")
        elif external_id in seen:
            row_errors.append("duplicate external_id in file")
        elif external_id in existing_ids:
            row_errors.append("external_id already exists")
        seen.add(external_id)
        try:
            raw_date = values["date"]
            if isinstance(raw_date, datetime):
                transaction_date = raw_date.date()
            elif isinstance(raw_date, date):
                transaction_date = raw_date
            else:
                transaction_date = date.fromisoformat(str(raw_date).strip())
        except (ValueError, TypeError):
            transaction_date = None
            row_errors.append("date must use YYYY-MM-DD")
        else:
            if settings.demo_mode and (transaction_date < DEMO_DATA_START or transaction_date > DEMO_DATA_END):
                row_errors.append(f"date must be between {DEMO_DATA_START.isoformat()} and {DEMO_DATA_END.isoformat()}")
        try:
            amount = Decimal(str(values["amount"]))
            if not amount.is_finite() or abs(amount) > Decimal("999999999999.99"):
                raise InvalidOperation
            rounded_amount = amount.quantize(Decimal("0.01"))
            if amount != rounded_amount:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            amount = None
            row_errors.append("amount must be a decimal with at most two fractional digits and 12 integer digits")
        customer = customer_by_name.get(customer_name)
        department = department_by_name.get(department_name)
        if not customer:
            row_errors.append("customer must match an existing organization customer")
        if not department:
            row_errors.append("department must match an existing organization department")
        currency = str(values["currency"] or "").strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            row_errors.append("currency must be a three-letter code")
        elif currency != organization_currency:
            row_errors.append(f"currency must match the workspace currency ({organization_currency})")
        description = str(values["description"] or "").strip()
        if not description:
            row_errors.append("description is required")
        elif len(description) > 240:
            row_errors.append("description cannot exceed 240 characters")
        if row_errors:
            errors.append({"row": row_number, "errors": row_errors})
        else:
            valid_rows.append(
                {
                    "external_id": external_id,
                    "date": transaction_date,
                    "customer": customer,
                    "department": department,
                    "amount": amount.quantize(Decimal("0.01")),
                    "currency": currency,
                    "description": description[:240],
                }
            )
    return {"valid_rows": valid_rows, "errors": errors, "total_rows": max(0, len(rows) - 1)}


@app.post("/api/v1/imports/revenue/preview")
async def preview_revenue_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    organization = context.organization
    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.upload_max_bytes // (1024 * 1024)} MB upload limit.")
    result = validate_revenue_import(content, file.filename or "", db, organization.id)
    return {
        "total_rows": result["total_rows"],
        "valid_rows": len(result["valid_rows"]),
        "invalid_rows": len(result["errors"]),
        "errors": result["errors"][:100],
        "preview": [
            {
                "external_id": row["external_id"],
                "date": row["date"].isoformat(),
                "customer": row["customer"].name,
                "department": row["department"].name,
                "amount": str(row["amount"]),
                "currency": row["currency"],
                "description": row["description"],
            }
            for row in result["valid_rows"][:10]
        ],
        "can_commit": result["total_rows"] > 0 and not result["errors"],
    }


@app.post("/api/v1/imports/revenue/commit")
async def commit_revenue_import(
    file: UploadFile = File(...),
    confirm: bool = Form(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required to commit an import.")
    organization = context.organization
    if settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo data is read-only.")
    if context.role not in {"owner", "admin", "analyst"}:
        raise HTTPException(status_code=403, detail="Insufficient organization permissions.")
    content = await file.read(settings.upload_max_bytes + 1)
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.upload_max_bytes // (1024 * 1024)} MB upload limit.")
    result = validate_revenue_import(content, file.filename or "", db, organization.id)
    if result["errors"] or not result["valid_rows"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "Import was not committed; fix all row errors and preview again.", "errors": result["errors"][:100]},
        )
    try:
        for row in result["valid_rows"]:
            db.add(
                RevenueTransaction(
                    organization_id=organization.id,
                    customer_id=row["customer"].id,
                    department_id=row["department"].id,
                    external_id=row["external_id"],
                    transaction_date=row["date"],
                    amount=row["amount"],
                    currency=row["currency"],
                    description=row["description"],
                    revenue_type="recognized",
                )
            )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="The import conflicts with an existing record; no records were committed.") from error
    except Exception:
        db.rollback()
        raise
    return {"status": "committed", "imported_rows": len(result["valid_rows"]), "synthetic_demo_data": organization.is_demo}


app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(crud_router)

web_dist = Path(__file__).resolve().parent / "static"
if not web_dist.is_dir():
    web_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if web_dist.is_dir():
    @app.get("/{asset_path:path}", include_in_schema=False)
    def serve_web_app(asset_path: str):
        if asset_path == "api" or asset_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = (web_dist / asset_path).resolve()
        if not candidate.is_relative_to(web_dist):
            raise HTTPException(status_code=404, detail="Not found.")
        if not candidate.is_file():
            candidate = web_dist / "index.html"
        return FileResponse(candidate)
