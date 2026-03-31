from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AreaCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    location_description: str = Field(default="", max_length=250)
    video_source: str = Field(..., min_length=1, max_length=500)
    threshold: int = Field(..., ge=1, le=500)
    authority_email: str = Field(..., min_length=5, max_length=200)
    alert_cooldown_seconds: int = Field(default=300, ge=30, le=86400)
    roi_x: Optional[int] = Field(default=None, ge=0)
    roi_y: Optional[int] = Field(default=None, ge=0)
    roi_width: Optional[int] = Field(default=None, ge=1)
    roi_height: Optional[int] = Field(default=None, ge=1)

    @field_validator("name", "location_description", "video_source", "authority_email")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("authority_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Please provide a valid authority email address.")
        return value

    @model_validator(mode="after")
    def validate_roi(self) -> "AreaCreate":
        roi_values = [self.roi_x, self.roi_y, self.roi_width, self.roi_height]
        if any(value is None for value in roi_values) and any(
            value is not None for value in roi_values
        ):
            raise ValueError("Provide all ROI values or leave them all blank.")
        return self


class AreaResponse(AreaCreate):
    id: int
    active: int
    created_at: str


class AreaUpdate(AreaCreate):
    pass


class MonitorStatusResponse(BaseModel):
    area_id: int
    area_name: str
    last_count: Optional[int] = None
    last_checked_at: Optional[str] = None
    state: str
    last_error: Optional[str] = None
    updated_at: str


class AlertResponse(BaseModel):
    id: int
    area_id: int
    area_name: str
    people_count: int
    threshold: int
    status: str
    email_status: str
    email_error: Optional[str] = None
    image_path: Optional[str] = None
    created_at: str


class ActionResponse(BaseModel):
    message: str
