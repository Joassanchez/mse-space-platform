"""Read-only SQLAlchemy ORM models for existing DB tables.

These models map to tables created and managed by the AI Core migrations.
The Backend API layer NEVER writes to these tables — SELECT only.

Sources: migrations/001 through 007 (actual DB schema).
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class AgentExecution(Base):
    """agent_executions — Módulo 5: Area Orchestrators & Hydric Environmental Agents.

    Migrations: 005 (create), 006 (id SERIAL → UUID).
    No direct region_id column — linked via workflow_id.
    """

    __tablename__ = "agent_executions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(PG_UUID, primary_key=True)
    agent_code: Mapped[str] = mapped_column(String(50))
    orchestrator_area: Mapped[str] = mapped_column(String(50))
    workflow_id: Mapped[str] = mapped_column(String(100))
    context_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    natural_language_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AiWorkflowState(Base):
    """ai_workflow_states — Módulo 4: AI Foundation.

    Tracks AI workflow lifecycle. Context JSONB may contain region info.
    """

    __tablename__ = "ai_workflow_states"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    workflow_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Region(Base):
    """regions — Módulo 3: Geospatial Storage.

    NOTE: Primary key is INTEGER id (SERIAL), NOT a string region_id.
    The string identifier used in the PRD (e.g. 'cordoba_pilot') would be in name or metadata_json.
    """

    __tablename__ = "regions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    name: Mapped[str] = mapped_column(String(255))
    region_type: Mapped[str] = mapped_column(String(50))
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bbox: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    """alerts — Módulo 3: Geospatial Storage.

    region_id is INTEGER FK to regions(id). No direct string region identifier.
    Status field: active, acknowledged, resolved, dismissed.
    """

    __tablename__ = "alerts"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    region_id: Mapped[int] = mapped_column()  # FK to regions(id)
    risk_assessment_id: Mapped[int | None] = mapped_column(nullable=True)
    alert_type: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionJob(Base):
    """ingestion_jobs — Módulo 1: SMAP Ingestion.

    Primary key is VARCHAR(50), not UUID.
    Has region_id as VARCHAR(100) — free-text region identifier.
    """

    __tablename__ = "ingestion_jobs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_id: Mapped[int] = mapped_column()  # FK to data_sources(id)
    dataset_id: Mapped[int | None] = mapped_column(nullable=True)
    region_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bbox: Mapped[list] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    ready_for_etl: Mapped[bool] = mapped_column(Boolean)
    search_only: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawFile(Base):
    """raw_files — Módulo 1: SMAP Ingestion."""

    __tablename__ = "raw_files"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    ingestion_job_id: Mapped[str] = mapped_column(String(50))
    source_id: Mapped[int] = mapped_column()
    dataset_id: Mapped[int | None] = mapped_column(nullable=True)
    granule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_product_id: Mapped[str] = mapped_column(String(100))
    remote_url: Mapped[str] = mapped_column(Text)
    acquisition_date: Mapped[datetime | None] = mapped_column(nullable=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(255))
    file_format: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column()
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ready_for_etl: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProcessedGeospatialLayer(Base):
    """processed_geospatial_layers — Módulo 2: ETL Geoespacial.

    Each row represents a processed GeoTIFF layer with spatial metadata.
    Closest match to the PRD's 'geo_layers' concept.
    """

    __tablename__ = "processed_geospatial_layers"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)  # SERIAL
    processing_job_id: Mapped[str] = mapped_column(String(50))
    raw_file_id: Mapped[int] = mapped_column()
    source_code: Mapped[str] = mapped_column(String(20))
    variable_name: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_path: Mapped[str] = mapped_column(Text)
    crs: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acquisition_date: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
