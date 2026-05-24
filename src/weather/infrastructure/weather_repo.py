"""PostgreSQL implementation of WeatherSnapshotRepository."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from src.weather.domain.interfaces import WeatherSnapshotRepository
from src.weather.domain.models import WeatherSnapshot

logger = logging.getLogger(__name__)


class WeatherSnapshotRepo(WeatherSnapshotRepository):
    """PostgreSQL implementation for weather_snapshots table."""

    def __init__(
        self,
        host: str | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        port: int | None = None,
    ):
        import os
        self._host = host or os.getenv("PGHOST", "localhost")
        self._database = database or os.getenv("PGDATABASE", "mse_platform")
        self._user = user or os.getenv("PGUSER", "mse_user")
        self._password = password or os.getenv("PGPASSWORD", "mse_pass")
        self._port = port or int(os.getenv("PGPORT", "5432"))
        self._conn: psycopg2.extensions.connection | None = None

    def _get_connection(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self._host, database=self._database,
                user=self._user, password=self._password, port=self._port,
            )
        return self._conn

    def save(self, snapshot: WeatherSnapshot) -> int:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO weather_snapshots
                    (region_id, observed_at, temp_celsius, humidity_pct,
                     wind_speed_ms, rainfall_mm, pressure_hpa,
                     weather_condition, source, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    snapshot.region_id, snapshot.observed_at,
                    snapshot.temp_celsius, snapshot.humidity_pct,
                    snapshot.wind_speed_ms, snapshot.rainfall_mm,
                    snapshot.pressure_hpa, snapshot.weather_condition,
                    snapshot.source,
                    json.dumps(snapshot.metadata) if snapshot.metadata else "{}",
                ),
            )
            snap_id = cur.fetchone()[0]
            conn.commit()
        logger.debug(f"Weather snapshot saved: id={snap_id}, region={snapshot.region_id}")
        return snap_id

    def find_by_region_and_date(
        self, region_id: int, date_from: str, date_to: str
    ) -> list[WeatherSnapshot]:
        conn = self._get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM weather_snapshots
                WHERE region_id = %s
                  AND observed_at >= %s::timestamptz
                  AND observed_at <= %s::timestamptz
                ORDER BY observed_at DESC
                """,
                (region_id, date_from, date_to),
            )
            return [self._row_to_snapshot(r) for r in cur.fetchall()]

    def find_latest_by_region(
        self, region_id: int
    ) -> Optional[WeatherSnapshot]:
        conn = self._get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM weather_snapshots
                WHERE region_id = %s
                ORDER BY observed_at DESC
                LIMIT 1
                """,
                (region_id,),
            )
            row = cur.fetchone()
            return self._row_to_snapshot(row) if row else None

    @staticmethod
    def _row_to_snapshot(row: dict) -> WeatherSnapshot:
        return WeatherSnapshot(
            id=row["id"],
            region_id=row["region_id"],
            observed_at=row["observed_at"].isoformat() if hasattr(row["observed_at"], "isoformat") else str(row["observed_at"]),
            temp_celsius=float(row["temp_celsius"]) if row["temp_celsius"] is not None else None,
            humidity_pct=float(row["humidity_pct"]) if row["humidity_pct"] is not None else None,
            wind_speed_ms=float(row["wind_speed_ms"]) if row["wind_speed_ms"] is not None else None,
            rainfall_mm=float(row["rainfall_mm"]) if row["rainfall_mm"] is not None else None,
            pressure_hpa=float(row["pressure_hpa"]) if row["pressure_hpa"] is not None else None,
            weather_condition=row.get("weather_condition", ""),
            source=row.get("source", "openweather"),
            metadata=row.get("metadata", {}),
            created_at=row.get("created_at").isoformat() if row.get("created_at") else None,
        )

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None
