from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from .config import settings
from .utils import utc_now_iso

_DB_LOCK = Lock()
_UNSET = object()


def _get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def initialize_database() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)

    schema = """
    CREATE TABLE IF NOT EXISTS areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        location_description TEXT NOT NULL DEFAULT '',
        video_source TEXT NOT NULL,
        threshold INTEGER NOT NULL,
        authority_email TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        roi_x INTEGER,
        roi_y INTEGER,
        roi_width INTEGER,
        roi_height INTEGER,
        alert_cooldown_seconds INTEGER NOT NULL DEFAULT 300,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_id INTEGER NOT NULL,
        people_count INTEGER NOT NULL,
        threshold INTEGER NOT NULL,
        status TEXT NOT NULL,
        email_status TEXT NOT NULL,
        email_error TEXT,
        image_path TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(area_id) REFERENCES areas(id)
    );

    CREATE TABLE IF NOT EXISTS monitor_status (
        area_id INTEGER PRIMARY KEY,
        last_count INTEGER,
        last_checked_at TEXT,
        state TEXT NOT NULL DEFAULT 'STOPPED',
        last_error TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(area_id) REFERENCES areas(id)
    );
    """

    with _DB_LOCK:
        with _get_connection() as connection:
            connection.executescript(schema)
            connection.commit()


def list_areas() -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM areas ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_area(area_id: int) -> dict[str, Any] | None:
    with _get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM areas WHERE id = ?",
            (area_id,),
        ).fetchone()
    return _row_to_dict(row)


def create_area(data: dict[str, Any]) -> dict[str, Any]:
    created_at = utc_now_iso()

    with _DB_LOCK:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO areas (
                    name,
                    location_description,
                    video_source,
                    threshold,
                    authority_email,
                    active,
                    roi_x,
                    roi_y,
                    roi_width,
                    roi_height,
                    alert_cooldown_seconds,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["name"],
                    data.get("location_description", ""),
                    data["video_source"],
                    data["threshold"],
                    data["authority_email"],
                    1,
                    data.get("roi_x"),
                    data.get("roi_y"),
                    data.get("roi_width"),
                    data.get("roi_height"),
                    data.get("alert_cooldown_seconds", 300),
                    created_at,
                ),
            )
            area_id = cursor.lastrowid
            connection.execute(
                """
                INSERT OR REPLACE INTO monitor_status (
                    area_id,
                    last_count,
                    last_checked_at,
                    state,
                    last_error,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (area_id, None, None, "STOPPED", None, created_at),
            )
            connection.commit()

    area = get_area(area_id)
    if area is None:
        raise RuntimeError("Area was created but could not be loaded back from the database.")
    return area


def update_area(area_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    with _DB_LOCK:
        with _get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE areas
                SET
                    name = ?,
                    location_description = ?,
                    video_source = ?,
                    threshold = ?,
                    authority_email = ?,
                    roi_x = ?,
                    roi_y = ?,
                    roi_width = ?,
                    roi_height = ?,
                    alert_cooldown_seconds = ?
                WHERE id = ?
                """,
                (
                    data["name"],
                    data.get("location_description", ""),
                    data["video_source"],
                    data["threshold"],
                    data["authority_email"],
                    data.get("roi_x"),
                    data.get("roi_y"),
                    data.get("roi_width"),
                    data.get("roi_height"),
                    data.get("alert_cooldown_seconds", 300),
                    area_id,
                ),
            )
            connection.commit()

    if cursor.rowcount == 0:
        return None
    return get_area(area_id)


def upsert_monitor_status(
    area_id: int,
    *,
    last_count: int | None | object = _UNSET,
    last_checked_at: str | None | object = _UNSET,
    state: str,
    last_error: str | None | object = _UNSET,
) -> None:
    updated_at = utc_now_iso()

    with _DB_LOCK:
        with _get_connection() as connection:
            existing = connection.execute(
                """
                SELECT last_count, last_checked_at, state, last_error
                FROM monitor_status
                WHERE area_id = ?
                """,
                (area_id,),
            ).fetchone()

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO monitor_status (
                        area_id,
                        last_count,
                        last_checked_at,
                        state,
                        last_error,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        area_id,
                        None if last_count is _UNSET else last_count,
                        None if last_checked_at is _UNSET else last_checked_at,
                        state,
                        None if last_error is _UNSET else last_error,
                        updated_at,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE monitor_status
                    SET
                        last_count = ?,
                        last_checked_at = ?,
                        state = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE area_id = ?
                    """,
                    (
                        existing["last_count"] if last_count is _UNSET else last_count,
                        existing["last_checked_at"]
                        if last_checked_at is _UNSET
                        else last_checked_at,
                        state,
                        existing["last_error"] if last_error is _UNSET else last_error,
                        updated_at,
                        area_id,
                    ),
                )
            connection.commit()


def list_monitor_status() -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                monitor_status.area_id,
                areas.name AS area_name,
                monitor_status.last_count,
                monitor_status.last_checked_at,
                monitor_status.state,
                monitor_status.last_error,
                monitor_status.updated_at
            FROM monitor_status
            INNER JOIN areas ON areas.id = monitor_status.area_id
            ORDER BY areas.name ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_alert(
    area_id: int,
    *,
    people_count: int,
    threshold: int,
    status: str,
    email_status: str,
    email_error: str | None,
    image_path: str | None,
    created_at: str,
) -> None:
    with _DB_LOCK:
        with _get_connection() as connection:
            connection.execute(
                """
                INSERT INTO alerts (
                    area_id,
                    people_count,
                    threshold,
                    status,
                    email_status,
                    email_error,
                    image_path,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    area_id,
                    people_count,
                    threshold,
                    status,
                    email_status,
                    email_error,
                    image_path,
                    created_at,
                ),
            )
            connection.commit()


def get_alert(alert_id: int) -> dict[str, Any] | None:
    with _get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                alerts.id,
                alerts.area_id,
                areas.name AS area_name,
                alerts.people_count,
                alerts.threshold,
                alerts.status,
                alerts.email_status,
                alerts.email_error,
                alerts.image_path,
                alerts.created_at
            FROM alerts
            INNER JOIN areas ON areas.id = alerts.area_id
            WHERE alerts.id = ?
            """,
            (alert_id,),
        ).fetchone()
    return _row_to_dict(row)


def list_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with _get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                alerts.id,
                alerts.area_id,
                areas.name AS area_name,
                alerts.people_count,
                alerts.threshold,
                alerts.status,
                alerts.email_status,
                alerts.email_error,
                alerts.image_path,
                alerts.created_at
            FROM alerts
            INNER JOIN areas ON areas.id = alerts.area_id
            ORDER BY alerts.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_area(area_id: int) -> tuple[bool, list[str]]:
    with _DB_LOCK:
        with _get_connection() as connection:
            alert_rows = connection.execute(
                "SELECT image_path FROM alerts WHERE area_id = ?",
                (area_id,),
            ).fetchall()
            area_row = connection.execute(
                "SELECT id FROM areas WHERE id = ?",
                (area_id,),
            ).fetchone()

            if area_row is None:
                return False, []

            connection.execute("DELETE FROM alerts WHERE area_id = ?", (area_id,))
            connection.execute("DELETE FROM monitor_status WHERE area_id = ?", (area_id,))
            connection.execute("DELETE FROM areas WHERE id = ?", (area_id,))
            connection.commit()

    image_paths = [
        row["image_path"]
        for row in alert_rows
        if row["image_path"]
    ]
    return True, image_paths
