"""Add account lifecycle, rate-limit, and audit tables."""

from alembic import op
import sqlalchemy as sa

revision = "0002_account_security"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "email_action_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_action_tokens_user_id", "email_action_tokens", ["user_id"])
    op.create_index("ix_email_action_tokens_token_hash", "email_action_tokens", ["token_hash"], unique=True)
    op.create_index("ix_email_action_tokens_expires_at", "email_action_tokens", ["expires_at"])
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key_hash", sa.String(length=64), primary_key=True),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("request_id", sa.String(length=36)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_org_created", "audit_events", ["organization_id", "created_at"])
    op.create_index("ix_audit_actor_created", "audit_events", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_actor_created", table_name="audit_events")
    op.drop_index("ix_audit_org_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_email_action_tokens_expires_at", table_name="email_action_tokens")
    op.drop_index("ix_email_action_tokens_token_hash", table_name="email_action_tokens")
    op.drop_index("ix_email_action_tokens_user_id", table_name="email_action_tokens")
    op.drop_table("email_action_tokens")
    op.drop_column("users", "email_verified")
