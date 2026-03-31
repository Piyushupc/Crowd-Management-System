from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import cv2

from . import database
from .config import settings
from .emailer import send_alert_email
from .utils import build_snapshot_path, should_trigger_alert, utc_now, video_source_value


class AreaMonitor(threading.Thread):
    def __init__(self, area_id: int) -> None:
        super().__init__(daemon=True)
        self.area_id = area_id
        self.stop_event = threading.Event()
        self.last_alert_at = None
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        capture = None
        database.upsert_monitor_status(self.area_id, state="STARTING", last_error=None)
        final_state = "STOPPED"
        final_error = None

        try:
            while not self.stop_event.is_set():
                area = database.get_area(self.area_id)
                if area is None:
                    final_state = "ERROR"
                    final_error = "Area configuration was not found."
                    return

                if capture is None:
                    capture = cv2.VideoCapture(video_source_value(area["video_source"]))
                    if not capture.isOpened():
                        capture.release()
                        capture = None
                        database.upsert_monitor_status(
                            self.area_id,
                            state="ERROR",
                            last_error="Unable to open the configured video source.",
                        )
                        self.stop_event.wait(settings.reconnect_delay_seconds)
                        continue

                ok, frame = capture.read()
                if not ok or frame is None:
                    capture.release()
                    capture = None
                    database.upsert_monitor_status(
                        self.area_id,
                        state="ERROR",
                        last_error="Video stream opened but no frame could be read.",
                    )
                    self.stop_event.wait(settings.reconnect_delay_seconds)
                    continue

                timestamp = utc_now()
                roi = self._build_roi(area)
                boxes = self._detect_people(frame, roi)
                people_count = len(boxes)

                database.upsert_monitor_status(
                    self.area_id,
                    last_count=people_count,
                    last_checked_at=timestamp.isoformat(),
                    state="RUNNING",
                    last_error=None,
                )

                if should_trigger_alert(
                    people_count,
                    area["threshold"],
                    self.last_alert_at,
                    area["alert_cooldown_seconds"],
                    now=timestamp,
                ):
                    snapshot_path = self._save_snapshot(
                        frame=frame,
                        area_name=area["name"],
                        boxes=boxes,
                        count=people_count,
                        threshold=area["threshold"],
                        roi=roi,
                        timestamp=timestamp,
                    )
                    email_status, email_error = send_alert_email(
                        area,
                        people_count=people_count,
                        threshold=area["threshold"],
                        timestamp=timestamp.isoformat(),
                        image_path=snapshot_path,
                    )
                    database.create_alert(
                        self.area_id,
                        people_count=people_count,
                        threshold=area["threshold"],
                        status="THRESHOLD_EXCEEDED",
                        email_status=email_status,
                        email_error=email_error,
                        image_path=snapshot_path,
                        created_at=timestamp.isoformat(),
                    )
                    self.last_alert_at = timestamp

                self.stop_event.wait(settings.detection_interval_seconds)
        except Exception as exc:
            final_state = "ERROR"
            final_error = str(exc)
        finally:
            if capture is not None:
                capture.release()
            database.upsert_monitor_status(
                self.area_id,
                state=final_state,
                last_error=final_error,
            )

    def _build_roi(self, area: dict[str, Any]) -> tuple[int, int, int, int] | None:
        roi_values = (
            area.get("roi_x"),
            area.get("roi_y"),
            area.get("roi_width"),
            area.get("roi_height"),
        )
        if any(value is None for value in roi_values):
            return None
        return tuple(int(value) for value in roi_values)

    def _detect_people(
        self,
        frame,
        roi: tuple[int, int, int, int] | None,
    ) -> list[list[int]]:
        x_offset = 0
        y_offset = 0
        region = frame

        if roi is not None:
            x, y, width, height = roi
            region = frame[y : y + height, x : x + width]
            x_offset = x
            y_offset = y

        if region is None or region.size == 0:
            return []

        height, width = region.shape[:2]
        resize_ratio = 1.0
        resized = region

        if width > 960:
            resize_ratio = width / 960.0
            resized = cv2.resize(region, (960, int(height / resize_ratio)))

        detections, weights = self.hog.detectMultiScale(
            resized,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.03,
        )

        boxes: list[list[int]] = []
        scores: list[float] = []
        for index, (x, y, box_width, box_height) in enumerate(detections):
            boxes.append(
                [
                    int(x * resize_ratio) + x_offset,
                    int(y * resize_ratio) + y_offset,
                    int(box_width * resize_ratio),
                    int(box_height * resize_ratio),
                ]
            )
            score = weights[index]
            scores.append(float(score[0] if hasattr(score, "__len__") else score))

        if not boxes:
            return []

        kept_indices = cv2.dnn.NMSBoxes(
            boxes,
            scores,
            score_threshold=0.0,
            nms_threshold=0.35,
        )
        if len(kept_indices) == 0:
            return boxes

        flattened = kept_indices.flatten().tolist()
        return [boxes[index] for index in flattened]

    def _save_snapshot(
        self,
        *,
        frame,
        area_name: str,
        boxes: list[list[int]],
        count: int,
        threshold: int,
        roi: tuple[int, int, int, int] | None,
        timestamp,
    ) -> str:
        annotated = frame.copy()

        if roi is not None:
            x, y, width, height = roi
            cv2.rectangle(annotated, (x, y), (x + width, y + height), (0, 255, 255), 2)

        for x, y, width, height in boxes:
            cv2.rectangle(annotated, (x, y), (x + width, y + height), (0, 0, 255), 2)

        cv2.putText(
            annotated,
            f"Count: {count}  Threshold: {threshold}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            annotated,
            timestamp.isoformat(),
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        snapshot_dir = Path(settings.snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        output_path = build_snapshot_path(snapshot_dir, area_name, timestamp)
        cv2.imwrite(str(output_path), annotated)
        return str(output_path)


class DetectorManager:
    def __init__(self) -> None:
        self._monitors: dict[int, AreaMonitor] = {}
        self._lock = threading.Lock()

    def start(self, area_id: int) -> tuple[bool, str]:
        area = database.get_area(area_id)
        if area is None:
            return False, "Area not found."

        with self._lock:
            current = self._monitors.get(area_id)
            if current is not None and current.is_alive():
                return False, f"Monitoring is already running for {area['name']}."

            monitor = AreaMonitor(area_id)
            self._monitors[area_id] = monitor
            monitor.start()

        return True, f"Monitoring started for {area['name']}."

    def is_running(self, area_id: int) -> bool:
        with self._lock:
            current = self._monitors.get(area_id)
            return current is not None and current.is_alive()

    def stop(self, area_id: int) -> tuple[bool, str]:
        with self._lock:
            current = self._monitors.get(area_id)
            if current is None:
                database.upsert_monitor_status(
                    area_id,
                    state="STOPPED",
                    last_error=None,
                )
                return False, "Monitoring is not currently running for this area."

            current.stop()

        current.join(timeout=5)
        if current.is_alive():
            database.upsert_monitor_status(
                area_id,
                state="STOPPING",
            )
            return False, "Monitoring is taking longer to stop. Please try again in a moment."

        with self._lock:
            self._monitors.pop(area_id, None)

        database.upsert_monitor_status(
            area_id,
            state="STOPPED",
            last_error=None,
        )
        return True, "Monitoring stopped."

    def start_active_monitors(self) -> None:
        for area in database.list_areas():
            if area["active"]:
                self.start(area["id"])

    def stop_all(self) -> None:
        with self._lock:
            active_monitors = list(self._monitors.items())

        for area_id, monitor in active_monitors:
            monitor.stop()
            monitor.join(timeout=5)
            database.upsert_monitor_status(
                area_id,
                state="STOPPED" if not monitor.is_alive() else "STOPPING",
                last_error=None if not monitor.is_alive() else "Shutdown is still in progress.",
            )

        with self._lock:
            self._monitors = {
                area_id: monitor
                for area_id, monitor in self._monitors.items()
                if monitor.is_alive()
            }


detector_manager = DetectorManager()
