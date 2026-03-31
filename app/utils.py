from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
    return cleaned.strip("-") or "area"


def video_source_value(value: str) -> int | str:
    source = str(value).strip()
    return int(source) if source.isdigit() else source


def should_trigger_alert(
    count: int,
    threshold: int,
    last_alert_at: datetime | None,
    cooldown_seconds: int,
    now: datetime | None = None,
) -> bool:
    if count <= threshold:
        return False
    if last_alert_at is None:
        return True

    current_time = now or utc_now()
    return (current_time - last_alert_at).total_seconds() >= cooldown_seconds


def build_snapshot_path(base_dir: str | Path, area_name: str, timestamp: datetime) -> Path:
    filename = f"{sanitize_name(area_name)}-{timestamp.strftime('%Y%m%d-%H%M%S')}.jpg"
    return Path(base_dir) / filename
