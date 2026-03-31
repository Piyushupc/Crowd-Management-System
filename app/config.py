from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


class Settings:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent

        self.app_name = os.getenv("APP_NAME", "CrowdSafe Monitor")
        self.database_path = str(
            _resolve_path(os.getenv("DATABASE_PATH", "crowdsafe.db"), base_dir)
        )
        self.snapshot_dir = str(
            _resolve_path(os.getenv("SNAPSHOT_DIR", "snapshots"), base_dir)
        )

        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = _env_int("SMTP_PORT", 587)
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_use_tls = _env_bool("SMTP_USE_TLS", True)
        self.sender_email = os.getenv("SENDER_EMAIL", "")
        self.alert_subject_prefix = os.getenv(
            "ALERT_SUBJECT_PREFIX", "[CrowdSafe Alert]"
        )

        self.detection_interval_seconds = _env_int("DETECTION_INTERVAL_SECONDS", 2)
        self.reconnect_delay_seconds = _env_int("RECONNECT_DELAY_SECONDS", 5)
        self.auto_start_monitors = _env_bool("AUTO_START_MONITORS", False)


settings = Settings()
