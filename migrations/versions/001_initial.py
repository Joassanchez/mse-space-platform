"""Initial schema — all core tables for ARGPLANT Data Service.

Creates: locations, weather_snapshots, satellite_scenes, price_series, ingestion_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- locations ---
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lon", sa.Double(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- weather_snapshots ---
    op.create_table(
        "weather_snapshots",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("temp", sa.Double(), nullable=True),
        sa.Column("humidity", sa.Integer(), nullable=True),
        sa.Column("wind_speed", sa.Double(), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'openweather'"), nullable=False),
        sa.Column("data", sa.JSONB(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
    )
    op.create_index(
        "idx_weather_loc_time",
        "weather_snapshots",
        ["location_id", "captured_at"],
    )

    # --- satellite_scenes ---
    op.create_table(
        "satellite_scenes",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scene_id", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("bbox", sa.JSONB(), nullable=False),
        sa.Column("acquisition_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloud_cover", sa.Double(), nullable=True),
        sa.Column("metadata", sa.JSONB(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_id"),
    )
    op.create_index(
        "idx_sat_scenes_platform",
        "satellite_scenes",
        ["platform", "acquisition_date"],
    )

    # --- price_series ---
    op.create_table(
        "price_series",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("puerto_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("minimo", sa.Double(), nullable=True),
        sa.Column("maximo", sa.Double(), nullable=True),
        sa.Column("promedio", sa.Double(), nullable=True),
        sa.Column("modal", sa.Double(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("producto_id", "puerto_id", "fecha"),
    )

    # --- ingestion_jobs ---
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("params", sa.JSONB(), nullable=False),
        sa.Column("result", sa.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jobs_status", "ingestion_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("idx_jobs_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_table("price_series")
    op.drop_index("idx_sat_scenes_platform", table_name="satellite_scenes")
    op.drop_table("satellite_scenes")
    op.drop_index("idx_weather_loc_time", table_name="weather_snapshots")
    op.drop_table("weather_snapshots")
    op.drop_table("locations")
