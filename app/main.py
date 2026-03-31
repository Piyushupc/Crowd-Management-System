from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from . import database
from .config import settings
from .detector import detector_manager
from .schemas import (
    ActionResponse,
    AlertResponse,
    AreaCreate,
    AreaResponse,
    AreaUpdate,
    MonitorStatusResponse,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SNAPSHOT_DIR = Path(settings.snapshot_dir).resolve()


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize_database()
    if settings.auto_start_monitors:
        detector_manager.start_active_monitors()
    yield
    detector_manager.stop_all()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": settings.app_name}


@app.get("/api/areas", response_model=list[AreaResponse])
def list_areas() -> list[dict]:
    return database.list_areas()


@app.post("/api/areas", response_model=AreaResponse, status_code=201)
def create_area(payload: AreaCreate) -> dict:
    try:
        return database.create_area(payload.model_dump())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=400,
            detail="Area name already exists. Please choose a unique name.",
        ) from exc


@app.put("/api/areas/{area_id}", response_model=AreaResponse)
def update_area(area_id: int, payload: AreaUpdate) -> dict:
    if database.get_area(area_id) is None:
        raise HTTPException(status_code=404, detail="Area not found.")

    was_running = detector_manager.is_running(area_id)
    if was_running:
        stopped, message = detector_manager.stop(area_id)
        if not stopped:
            raise HTTPException(status_code=409, detail=message)

    try:
        area = database.update_area(area_id, payload.model_dump())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=400,
            detail="Area name already exists. Please choose a unique name.",
        ) from exc

    if area is None:
        raise HTTPException(status_code=404, detail="Area not found.")

    if was_running:
        detector_manager.start(area_id)
    return area


@app.delete("/api/areas/{area_id}", response_model=ActionResponse)
def delete_area(area_id: int) -> dict[str, str]:
    if detector_manager.is_running(area_id):
        stopped, message = detector_manager.stop(area_id)
        if not stopped:
            raise HTTPException(status_code=409, detail=message)

    deleted, image_paths = database.delete_area(area_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Area not found.")

    for image_path in image_paths:
        _remove_snapshot_file(image_path)

    return {"message": "Area deleted successfully."}


@app.post("/api/areas/{area_id}/monitor/start", response_model=ActionResponse)
def start_monitoring(area_id: int) -> dict[str, str]:
    started, message = detector_manager.start(area_id)
    if not started and message == "Area not found.":
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}


@app.post("/api/areas/{area_id}/monitor/stop", response_model=ActionResponse)
def stop_monitoring(area_id: int) -> dict[str, str]:
    area = database.get_area(area_id)
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found.")
    _, message = detector_manager.stop(area_id)
    return {"message": message}


@app.get("/api/status", response_model=list[MonitorStatusResponse])
def list_status() -> list[dict]:
    return database.list_monitor_status()


@app.get("/api/alerts", response_model=list[AlertResponse])
def list_alerts(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    return database.list_alerts(limit=limit)


@app.get("/api/alerts/{alert_id}/snapshot")
def get_alert_snapshot(alert_id: int) -> FileResponse:
    alert = database.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    if not alert["image_path"]:
        raise HTTPException(status_code=404, detail="This alert has no saved snapshot.")

    snapshot_path = Path(alert["image_path"]).resolve()
    if SNAPSHOT_DIR != snapshot_path and SNAPSHOT_DIR not in snapshot_path.parents:
        raise HTTPException(status_code=400, detail="Snapshot path is outside the allowed directory.")
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file was not found.")

    return FileResponse(snapshot_path)


def _remove_snapshot_file(image_path: str) -> None:
    snapshot_path = Path(image_path).resolve()
    if SNAPSHOT_DIR != snapshot_path and SNAPSHOT_DIR not in snapshot_path.parents:
        return
    try:
        if snapshot_path.exists():
            snapshot_path.unlink()
    except OSError:
        return
