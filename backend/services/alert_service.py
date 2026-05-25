"""Alert service — queries alerts table with region joins."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.alerts import (
    AlertItem,
    AlertListResponse,
    AlertDetailResponse,
    ActiveAlertCountResponse,
)

# Severity ordering for consistent sorting
SEVERITY_ORDER = {"critical": 0, "severe": 1, "warning": 2, "info": 3}


async def get_alerts(
    db: AsyncSession,
    region_id: int | None = None,
    severity: str | None = None,
    status: str | None = "active",
    page: int = 1,
    limit: int = 20,
) -> AlertListResponse:
    """List alerts with optional filters, ordered by severity then date."""
    conditions = ["1=1"]
    params: dict = {}

    if region_id is not None:
        conditions.append("a.region_id = :region_id")
        params["region_id"] = region_id
    if severity:
        conditions.append("a.severity = :severity")
        params["severity"] = severity
    if status:
        conditions.append("a.status = :status")
        params["status"] = status

    where = " AND ".join(conditions)
    offset = (page - 1) * limit

    # Count
    count_sql = f"SELECT COUNT(*) FROM alerts a WHERE {where}"
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar() or 0

    # Data
    data_sql = f"""
        SELECT a.id, a.alert_type, a.severity, a.title, a.status,
               a.region_id, r.name AS region_name,
               a.issued_at, a.created_at
        FROM alerts a
        LEFT JOIN regions r ON r.id = a.region_id
        WHERE {where}
        ORDER BY
            CASE a.severity
                WHEN 'critical' THEN 0
                WHEN 'severe' THEN 1
                WHEN 'warning' THEN 2
                WHEN 'info' THEN 3
                ELSE 4
            END,
            a.issued_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset
    result = await db.execute(text(data_sql), params)
    rows = result.fetchall()

    items = [
        AlertItem(
            id=row[0],
            alert_type=row[1],
            severity=row[2],
            title=row[3],
            status=row[4],
            region_id=row[5],
            region_name=row[6],
            issued_at=row[7],
            created_at=row[8],
        )
        for row in rows
    ]

    return AlertListResponse(items=items, total=total)


async def get_alert_detail(
    db: AsyncSession,
    alert_id: int,
) -> AlertDetailResponse | None:
    """Get full detail for a single alert."""
    sql = """
        SELECT a.id, a.alert_type, a.severity, a.title, a.message,
               a.status, a.region_id, r.name AS region_name,
               a.issued_at, a.resolved_at, a.metadata,
               a.created_at
        FROM alerts a
        LEFT JOIN regions r ON r.id = a.region_id
        WHERE a.id = :alert_id
    """
    result = await db.execute(text(sql), {"alert_id": alert_id})
    row = result.fetchone()
    if not row:
        return None

    return AlertDetailResponse(
        id=row[0],
        alert_type=row[1],
        severity=row[2],
        title=row[3],
        message=row[4],
        status=row[5],
        region_id=row[6],
        region_name=row[7],
        issued_at=row[8],
        resolved_at=row[9],
        metadata=row[10],
        created_at=row[11],
    )


async def get_active_alert_count(
    db: AsyncSession,
    region_id: int | None = None,
) -> ActiveAlertCountResponse:
    """Count active alerts grouped by severity."""
    conditions = ["a.status = 'active'"]
    params: dict = {}
    if region_id is not None:
        conditions.append("a.region_id = :region_id")
        params["region_id"] = region_id

    where = " AND ".join(conditions)
    sql = f"""
        SELECT a.severity, COUNT(*) AS cnt
        FROM alerts a
        WHERE {where}
        GROUP BY a.severity
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    counts = ActiveAlertCountResponse()
    for row in rows:
        sev = row[0]
        cnt = row[1]
        if sev == "critical":
            counts.critical = cnt
        elif sev == "severe":
            counts.severe = cnt
        elif sev == "warning":
            counts.warning = cnt
        elif sev == "info":
            counts.info = cnt
    counts.total = counts.critical + counts.severe + counts.warning + counts.info
    return counts


async def acknowledge_alert(
    db: AsyncSession,
    alert_id: int,
) -> bool:
    """Mark an alert as acknowledged. Returns True if updated."""
    from sqlalchemy import text as sql_text
    result = await db.execute(
        sql_text(
            "UPDATE alerts SET status = 'acknowledged' WHERE id = :id AND status = 'active'"
        ),
        {"id": alert_id},
    )
    await db.commit()
    return result.rowcount > 0
