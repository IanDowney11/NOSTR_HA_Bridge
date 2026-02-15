"""Pydantic models for NOSTR event payloads routed into Home Assistant."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Only lowercase alphanumeric and underscores — no path traversal or special chars
ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")


class SensorPayload(BaseModel):
    type: Literal["sensor"] = "sensor"
    entity_id: str = Field(..., description="Unique ID for this sensor (e.g. 'outdoor_temperature')")
    value: float | int | str
    unit: str = ""
    device_class: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if not ENTITY_ID_PATTERN.match(v):
            raise ValueError(f"entity_id must match [a-z0-9_]{{1,64}}, got: {v!r}")
        return v


class BinarySensorPayload(BaseModel):
    type: Literal["binary_sensor"] = "binary_sensor"
    entity_id: str = Field(..., description="Unique ID for this binary sensor (e.g. 'front_door')")
    state: bool
    device_class: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if not ENTITY_ID_PATTERN.match(v):
            raise ValueError(f"entity_id must match [a-z0-9_]{{1,64}}, got: {v!r}")
        return v


class NotificationPayload(BaseModel):
    type: Literal["notification"] = "notification"
    title: str = ""
    message: str
    severity: Literal["info", "warning", "error", "critical"] = "info"


# Union type for routing
PayloadType = SensorPayload | BinarySensorPayload | NotificationPayload

PAYLOAD_TYPE_MAP: dict[str, type[BaseModel]] = {
    "sensor": SensorPayload,
    "binary_sensor": BinarySensorPayload,
    "notification": NotificationPayload,
}
