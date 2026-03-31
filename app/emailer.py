from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from .config import settings


def _is_email_configured() -> bool:
    return bool(settings.smtp_host and settings.sender_email)


def send_alert_email(
    area: dict[str, Any],
    *,
    people_count: int,
    threshold: int,
    timestamp: str,
    image_path: str | None = None,
) -> tuple[str, str | None]:
    if not _is_email_configured():
        return "SKIPPED", "SMTP is not configured. Alert saved locally only."

    message = EmailMessage()
    message["Subject"] = f"{settings.alert_subject_prefix} {area['name']}"
    message["From"] = settings.sender_email
    message["To"] = area["authority_email"]
    message.set_content(
        "\n".join(
            [
                "Crowd threshold exceeded.",
                "",
                f"Area: {area['name']}",
                f"Location: {area['location_description'] or 'Not provided'}",
                f"Current people count: {people_count}",
                f"Safe threshold: {threshold}",
                f"Timestamp (UTC): {timestamp}",
                "",
                "Please review the area immediately.",
            ]
        )
    )

    if image_path:
        file_path = Path(image_path)
        if file_path.exists():
            mime_type, _ = mimetypes.guess_type(file_path.name)
            maintype, subtype = (mime_type or "image/jpeg").split("/", 1)
            with file_path.open("rb") as image_file:
                message.add_attachment(
                    image_file.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=file_path.name,
                )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return "SENT", None
    except Exception as exc:  # pragma: no cover - depends on external SMTP service
        return "FAILED", str(exc)
