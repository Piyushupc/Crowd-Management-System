from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.utils import should_trigger_alert, video_source_value


def test_video_source_value_returns_camera_index_for_numeric_inputs() -> None:
    assert video_source_value("0") == 0
    assert video_source_value("7") == 7


def test_video_source_value_keeps_stream_urls_as_text() -> None:
    assert video_source_value("rtsp://camera-01") == "rtsp://camera-01"


def test_should_trigger_alert_blocks_when_below_threshold() -> None:
    now = datetime.now(timezone.utc)
    assert should_trigger_alert(9, 10, None, 300, now=now) is False


def test_should_trigger_alert_respects_cooldown() -> None:
    now = datetime.now(timezone.utc)
    last_alert = now - timedelta(seconds=120)
    assert should_trigger_alert(12, 10, last_alert, 300, now=now) is False


def test_should_trigger_alert_allows_alert_after_cooldown() -> None:
    now = datetime.now(timezone.utc)
    last_alert = now - timedelta(seconds=600)
    assert should_trigger_alert(12, 10, last_alert, 300, now=now) is True
