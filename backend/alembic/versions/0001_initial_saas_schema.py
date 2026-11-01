"""Initial Vantage IQ SaaS schema, including the existing demo data model."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _create_table(name, *columns, **kwargs) -> None:
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, **kwargs)


def _create_index(name, table_name, columns, **kwargs) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, **kwargs)


def upgrade() -> None:
    _create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _create_index("ix_users_email", "users", ["email"], unique=True)
    _create_table(
        "organization_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'analyst', 'viewer')", name="ck_membership_role"),
    )
    _create_index("ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"])
    _create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
    _create_table(
        "login_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("active_organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    _create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    _create_index("ix_login_sessions_token_hash", "login_sessions", ["token_hash"], unique=True)
    _create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])
    _create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("organization_id", "name"),
    )
    _create_index("ix_departments_organization_id", "departments", ["organization_id"])
    _create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("segment", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("account_owner", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("organization_id", "name"),
    )
    _create_index("ix_customers_organization_id", "customers", ["organization_id"])
    _create_table(
        "revenue_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("revenue_type", sa.String(length=24), nullable=False),
        sa.UniqueConstraint("organization_id", "external_id", name="uq_revenue_org_external"),
    )
    _create_index("ix_revenue_org_date", "revenue_transactions", ["organization_id", "transaction_date"])
    _create_table(
        "expense_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=False),
    )
    _create_index("ix_expense_org_date", "expense_transactions", ["organization_id", "transaction_date"])
    _create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("revenue_target", sa.Numeric(14, 2), nullable=False),
        sa.Column("expense_budget", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("organization_id", "period_start", "department_id"),
    )
    _create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("manager", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("planned_end_date", sa.Date(), nullable=False),
        sa.Column("actual_end_date", sa.Date()),
        sa.Column("budget", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("planned_progress", sa.Integer(), nullable=False),
        sa.Column("actual_progress", sa.Integer(), nullable=False),
    )
    _create_index("ix_projects_organization_id", "projects", ["organization_id"])
    _create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.String(length=300), nullable=False),
        sa.Column("suggested_action", sa.String(length=300), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False),
    )
    _create_index("ix_alerts_organization_id", "alerts", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_organization_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("budgets")
    op.drop_index("ix_expense_org_date", table_name="expense_transactions")
    op.drop_table("expense_transactions")
    op.drop_index("ix_revenue_org_date", table_name="revenue_transactions")
    op.drop_table("revenue_transactions")
    op.drop_index("ix_customers_organization_id", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_departments_organization_id", table_name="departments")
    op.drop_table("departments")
    op.drop_index("ix_login_sessions_expires_at", table_name="login_sessions")
    op.drop_index("ix_login_sessions_token_hash", table_name="login_sessions")
    op.drop_index("ix_login_sessions_user_id", table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_organization_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
