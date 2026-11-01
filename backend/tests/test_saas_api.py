import pytest
from fastapi.testclient import TestClient
from fastapi import Request
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Customer, Organization, OrganizationMembership


@pytest.fixture
def client():
    previous_demo_mode = settings.demo_mode
    previous_cookie_secure = settings.session_cookie_secure
    previous_allow_registration = settings.allow_registration
    settings.demo_mode = False
    settings.session_cookie_secure = False
    settings.allow_registration = True
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app.state.test_action_emails = []
    app.state.test_sessions = test_sessions

    def capture_email(recipient: str, subject: str, action_url: str, action_label: str) -> None:
        app.state.test_action_emails.append(action_url)

    from app import security
    from app.main import EXPECTED_MIGRATION_REVISION

    previous_sender = security.send_action_email
    security.send_action_email = capture_email

    def override_get_db(request: Request):
        with test_sessions() as db:
            db.info["request_id"] = getattr(request.state, "request_id", None)
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with test_sessions() as db:
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:revision)"), {"revision": EXPECTED_MIGRATION_REVISION})
        db.commit()
    with TestClient(app) as test_client:
        yield test_client, test_sessions
    app.dependency_overrides.clear()
    security.send_action_email = previous_sender
    Base.metadata.drop_all(engine)
    app.state.test_action_emails = []
    del app.state.test_sessions
    engine.dispose()
    settings.demo_mode = previous_demo_mode
    settings.session_cookie_secure = previous_cookie_secure
    settings.allow_registration = previous_allow_registration


def register(client: TestClient, email: str):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery", "organization_name": "Acme"},
    )
    assert response.status_code == 202
    assert not response.headers.get("set-cookie")
    action_url = client.app.state.test_action_emails[-1]
    from urllib.parse import parse_qs, urlsplit

    token = parse_qs(urlsplit(action_url).query)["token"][0]
    verified = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    return response.json()


def test_registration_cookie_session_and_revocation(client):
    client, _ = client
    result = register(client, "Owner@example.com")
    assert client.cookies.get("vantage_csrf") == result["csrf_token"]
    assert result["user"]["email"] == "owner@example.com"
    assert result["memberships"][0]["role"] == "owner"
    assert result["active_organization_id"] == result["memberships"][0]["organization_id"]
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["memberships"][0]["organization_name"] == "Acme"
    assert me.json()["active_organization_id"] == result["active_organization_id"]
    assert "csrf_token" not in me.json()
    assert me.headers.get("x-request-id")

    csrf_from_cookie = client.cookies.get("vantage_csrf")
    created = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": csrf_from_cookie},
        json={"name": "Cookie CSRF", "segment": "Technology", "status": "Active", "account_owner": "Sam"},
    )
    assert created.status_code == 201

    logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": result["csrf_token"]})
    assert logout.status_code == 200
    assert client.cookies.get("vantage_csrf") is None
    assert client.get("/api/v1/auth/me").status_code == 401


def test_registration_can_be_disabled_by_configuration(client):
    client, _ = client
    settings.allow_registration = False
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "closed@example.com", "password": "correct horse battery", "organization_name": "Acme"},
    )
    assert response.status_code == 404
    assert client.get("/api/v1/config").json()["registration_enabled"] is False


def test_organization_switch_requires_membership_and_changes_active_org(client):
    client, sessions = client
    auth = register(client, "switch@example.com")
    owner_id = auth["user"]["id"]
    with sessions() as db:
        other = Organization(name="Second org", currency="USD")
        db.add(other)
        db.flush()
        db.add(OrganizationMembership(user_id=owner_id, organization_id=other.id, role="analyst"))
        db.commit()
        other_id = other.id

    assert client.get("/api/v1/auth/me").json()["active_organization_id"] == auth["active_organization_id"]
    switched = client.post(
        f"/api/v1/organizations/{other_id}/switch",
        headers={"X-CSRF-Token": auth["csrf_token"]},
    )
    assert switched.status_code == 200
    assert client.get("/api/v1/auth/me").json()["active_organization_id"] == other_id
    assert client.get("/api/v1/organizations").status_code == 200

    with TestClient(app) as outsider:
        outsider_auth = register(outsider, "outsider@example.com")
        denied = outsider.post(
            f"/api/v1/organizations/{other_id}/switch",
            headers={"X-CSRF-Token": outsider_auth["csrf_token"]},
        )
        assert denied.status_code == 404
        denied_selection = outsider.get(
            "/api/v1/customers",
            headers={"X-Organization-ID": str(other_id)},
        )
        assert denied_selection.status_code == 404


def test_crud_derives_tenant_and_enforces_roles(client):
    client, sessions = client
    owner = register(client, "tenant-owner@example.com")
    create = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": owner["csrf_token"]},
        json={"name": "Northwind", "segment": "Technology", "status": "Active", "account_owner": "Sam"},
    )
    assert create.status_code == 201
    customer_id = create.json()["id"]
    assert client.get("/api/v1/customers").json()["items"][0]["id"] == customer_id
    with sessions() as db:
        other_org = Organization(name="Not this tenant", currency="USD")
        db.add(other_org)
        db.flush()
        other_customer = Customer(
            organization_id=other_org.id,
            name="Private customer",
            segment="Private",
            status="Active",
            account_owner="Other user",
        )
        db.add(other_customer)
        db.commit()
        other_customer_id = other_customer.id
    assert client.get(f"/api/v1/customers/{other_customer_id}").status_code == 404
    assert client.get("/api/v1/customers").json()["items"][0]["name"] == "Northwind"
    injected_tenant = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": owner["csrf_token"]},
        json={
            "organization_id": owner["active_organization_id"],
            "name": "Rejected",
            "segment": "Technology",
            "status": "Active",
            "account_owner": "Sam",
        },
    )
    assert injected_tenant.status_code == 422

    with sessions() as db:
        membership = db.query(OrganizationMembership).filter_by(
            organization_id=owner["active_organization_id"], user_id=owner["user"]["id"]
        ).one()
        membership.role = "viewer"
        db.commit()
    denied = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": owner["csrf_token"]},
        json={"name": "Blocked", "segment": "Technology", "status": "Active", "account_owner": "Sam"},
    )
    assert denied.status_code == 403


def test_analytics_and_pdf_routes_are_available_for_authenticated_tenants(client):
    client, _ = client
    register(client, "reports@example.com")

    revenue = client.get("/api/v1/revenue/analytics?start_date=2026-01-01&end_date=2026-01-31")
    assert revenue.status_code == 200
    assert revenue.json()["recognized_revenue_by_customer"] == []
    assert revenue.json()["pipeline"] == []

    report = client.get("/api/v1/reports/executive.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"
    assert report.content.startswith(b"%PDF")


def test_business_resource_crud_and_pagination(client):
    client, _ = client
    owner = register(client, "crud@example.com")
    headers = {"X-CSRF-Token": owner["csrf_token"]}

    department = client.post("/api/v1/departments", headers=headers, json={"name": "Operations"}).json()
    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Contoso", "segment": "Technology", "status": "Active", "account_owner": "Alex"},
    ).json()
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "customer_id": customer["id"],
            "department_id": department["id"],
            "name": "Platform launch",
            "manager": "Jordan",
            "status": "In progress",
            "start_date": "2026-01-01",
            "planned_end_date": "2026-12-31",
            "budget": "10000.00",
            "actual_cost": "2500.00",
            "planned_progress": 50,
            "actual_progress": 40,
        },
    )
    budget = client.post(
        "/api/v1/budgets",
        headers=headers,
        json={
            "department_id": department["id"],
            "period_start": "2026-01-01",
            "revenue_target": "20000.00",
            "expense_budget": "5000.00",
        },
    ).json()
    revenue = client.post(
        "/api/v1/revenue",
        headers=headers,
        json={
            "customer_id": customer["id"],
            "department_id": department["id"],
            "external_id": "revenue-001",
            "transaction_date": "2026-01-15",
            "amount": "1250.00",
            "currency": "USD",
            "description": "January services",
        },
    )
    expense = client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "department_id": department["id"],
            "transaction_date": "2026-01-16",
            "amount": "300.00",
            "category": "Travel",
            "description": "Client visit",
        },
    ).json()

    assert project.status_code == 201
    assert revenue.status_code == 201
    for collection in ("departments", "customers", "projects", "budgets", "revenue", "expenses"):
        result = client.get(f"/api/v1/{collection}?limit=1&offset=0")
        assert result.status_code == 200
        assert result.json()["limit"] == 1
        assert len(result.json()["items"]) == 1

    updated = client.patch(
        f"/api/v1/projects/{project.json()['id']}",
        headers=headers,
        json={"actual_progress": 65},
    )
    assert updated.status_code == 200
    assert updated.json()["actual_progress"] == 65

    for collection, record in (
        ("expenses", expense),
        ("revenue", revenue.json()),
        ("budgets", budget),
        ("projects", project.json()),
        ("customers", customer),
        ("departments", department),
    ):
        deleted = client.delete(f"/api/v1/{collection}/{record['id']}", headers=headers)
        assert deleted.status_code == 204


def test_analyst_can_edit_but_cannot_delete_records(client):
    client, sessions = client
    owner = register(client, "analyst@example.com")
    headers = {"X-CSRF-Token": owner["csrf_token"]}
    customer = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Analyst account", "segment": "Services", "status": "Active", "account_owner": "Lee"},
    ).json()
    with sessions() as db:
        membership = db.query(OrganizationMembership).filter_by(
            organization_id=owner["active_organization_id"],
            user_id=owner["user"]["id"],
        ).one()
        membership.role = "analyst"
        db.commit()

    updated = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=headers,
        json={"status": "At risk"},
    )
    assert updated.status_code == 200
    denied = client.delete(f"/api/v1/customers/{customer['id']}", headers=headers)
    assert denied.status_code == 403


def test_login_uses_same_cookie_contract(client):
    client, _ = client
    initial = register(client, "login@example.com")
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": initial["csrf_token"]})
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    assert response.json()["memberships"][0]["organization_name"] == "Acme"
    assert response.json()["active_organization_id"] is not None


def test_email_verification_is_required_and_tokens_are_one_time(client):
    client, _ = client
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "correct horse battery", "organization_name": "Acme"},
    )
    assert registered.status_code == 202
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "verify@example.com", "password": "correct horse battery"},
    ).status_code == 401
    from urllib.parse import parse_qs, urlsplit

    token = parse_qs(urlsplit(client.app.state.test_action_emails[-1]).query)["token"][0]
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "verify@example.com", "password": "correct horse battery"},
    ).status_code == 200


def test_password_reset_revokes_existing_sessions(client):
    client, _ = client
    owner = register(client, "recovery@example.com")
    previous_cookie = client.cookies.get("vantage_session")
    assert client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "recovery@example.com"},
    ).status_code == 202
    from urllib.parse import parse_qs, urlsplit

    token = parse_qs(urlsplit(client.app.state.test_action_emails[-1]).query)["token"][0]
    reset = client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": token, "password": "a new correct horse battery"},
    )
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.cookies.get("vantage_session") == previous_cookie
    assert client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": token, "password": "another correct horse battery"},
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "recovery@example.com", "password": "a new correct horse battery"},
    ).status_code == 200


def test_email_delivery_failures_are_logged_without_account_enumeration(client, monkeypatch, caplog):
    client, _ = client
    register(client, "delivery@example.com")

    from app import security
    from app.email_delivery import EmailDeliveryError

    def fail_delivery(*args, **kwargs):
        raise EmailDeliveryError("relay unavailable")

    monkeypatch.setattr(security, "send_action_email", fail_delivery)
    known = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "delivery@example.com"},
    )
    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"status": "request_received"}
    assert "Account action email delivery failed" in caplog.text


def test_audit_history_is_persistent_tenant_scoped_and_admin_only(client):
    client, _ = client
    owner = register(client, "audit@example.com")
    headers = {"X-CSRF-Token": owner["csrf_token"]}
    created = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Audited", "segment": "Technology", "status": "Active", "account_owner": "Sam"},
    )
    assert created.status_code == 201
    events = client.get("/api/v1/audit-events")
    assert events.status_code == 200
    items = events.json()["items"]
    event = next(item for item in items if item["entity_type"] == "customers" and item["entity_id"] == created.json()["id"])
    assert event["action"] == "created"
    assert event["actor_email"] == "audit@example.com"
    assert event["request_id"]

    with TestClient(app) as outsider:
        outside = register(outsider, "other-audit@example.com")
        denied = outsider.get("/api/v1/audit-events")
        assert denied.status_code == 200
        assert all(item["actor_email"] != "audit@example.com" for item in denied.json()["items"])

    with client.app.state.test_sessions() as db:
        membership = db.query(OrganizationMembership).filter_by(
            organization_id=owner["active_organization_id"],
            user_id=owner["user"]["id"],
        ).one()
        membership.role = "analyst"
        db.commit()
    assert client.get("/api/v1/audit-events").status_code == 403


def test_readiness_checks_database_and_migration_head(client):
    client, sessions = client
    assert client.get("/api/v1/ready").json()["status"] == "ready"
    with sessions() as db:
        db.execute(text("UPDATE alembic_version SET version_num = '0001_initial'"))
        db.commit()
    assert client.get("/api/v1/ready").status_code == 503
