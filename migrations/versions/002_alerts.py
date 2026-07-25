"""Add alerts table with NOTIFY trigger for real-time SSE.

Creates:
  - alerts table (region_id, alert_type, severity, title, message, status, metadata)
  - notify_alert() function + trigger that fires NOTIFY on INSERT
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_alerts"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("region_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default=sa.text("'info'")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alerts_region_type", "alerts", ["region_id", "alert_type"])
    op.create_index("idx_alerts_status", "alerts", ["status"])

    # NOTIFY trigger function
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION notify_new_alert()
        RETURNS trigger AS $$
        BEGIN
            PERFORM pg_notify(
                'new_alert',
                json_build_object(
                    'id', NEW.id,
                    'title', NEW.title,
                    'severity', NEW.severity,
                    'alert_type', NEW.alert_type,
                    'region_id', NEW.region_id
                )::text
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """))

    # Attach trigger to alerts table
    op.execute(sa.text("""
        CREATE TRIGGER trigger_new_alert
        AFTER INSERT ON alerts
        FOR EACH ROW
        EXECUTE FUNCTION notify_new_alert();
    """))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trigger_new_alert ON alerts"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS notify_new_alert()"))
    op.drop_index("idx_alerts_status", table_name="alerts")
    op.drop_index("idx_alerts_region_type", table_name="alerts")
    op.drop_table("alerts")
