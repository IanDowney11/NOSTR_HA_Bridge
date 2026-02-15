"""Event router — parses decrypted JSON and dispatches to Home Assistant."""

import json
import logging
import re

from nostr_sdk import Event

from .ha_client import HomeAssistantClient
from .mealplanner import MealPlannerHandler
from .models import (
    PAYLOAD_TYPE_MAP,
    BinarySensorPayload,
    NotificationPayload,
    SensorPayload,
)

logger = logging.getLogger(__name__)

# Strip control characters (except newline/tab) to prevent log injection
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


class EventRouter:
    """Routes decrypted NOSTR event payloads to the appropriate HA handler."""

    def __init__(self, ha_client: HomeAssistantClient, entity_prefix: str = "nostr"):
        self._ha = ha_client
        self._prefix = entity_prefix
        self._mealplanner = MealPlannerHandler(ha_client, entity_prefix)

    async def refresh_daily(self) -> None:
        """Called periodically to handle date rollovers."""
        await self._mealplanner.refresh_today()

    async def handle_event(self, plaintext: str, event: Event) -> None:
        """Parse a decrypted JSON payload and route it to HA.

        This is the callback passed to RelayManager.
        """
        # Extract the d-tag to detect app-specific events (e.g., MyMealPlanner)
        d_tag = self._get_d_tag(event)

        if d_tag and d_tag.startswith("mmp:"):
            await self._handle_mealplanner_event(plaintext, d_tag, event)
            return

        # Standard bridge payload format
        try:
            raw = json.loads(plaintext)
        except json.JSONDecodeError:
            safe_preview = _CONTROL_CHARS.sub("", plaintext[:200])
            logger.error("Event %s: content is not valid JSON: %s", event.id().to_hex()[:12], safe_preview)
            return

        payload_type = raw.get("type")
        if not payload_type:
            logger.debug("Event %s: no 'type' field — skipping", event.id().to_hex()[:12])
            return

        model_cls = PAYLOAD_TYPE_MAP.get(payload_type)
        if not model_cls:
            logger.warning("Event %s: unknown payload type '%s'", event.id().to_hex()[:12], payload_type)
            return

        try:
            payload = model_cls.model_validate(raw)
        except Exception:
            logger.exception("Event %s: payload validation failed for type '%s'", event.id().to_hex()[:12], payload_type)
            return

        await self._dispatch(payload)

    async def _handle_mealplanner_event(self, plaintext: str, d_tag: str, event: Event) -> None:
        """Route a MyMealPlanner event to the appropriate handler."""
        try:
            raw = json.loads(plaintext)
        except json.JSONDecodeError:
            logger.error("MMP event %s: content is not valid JSON", event.id().to_hex()[:12])
            return

        parts = d_tag.split(":")
        entity_type = parts[1] if len(parts) > 1 else None

        if entity_type == "plan":
            await self._mealplanner.handle_plan_event(raw, d_tag)
        else:
            logger.debug("MMP event %s: ignoring entity type '%s'", event.id().to_hex()[:12], entity_type)

    async def _dispatch(self, payload: SensorPayload | BinarySensorPayload | NotificationPayload) -> None:
        match payload:
            case SensorPayload():
                entity_id = f"sensor.{self._prefix}_{payload.entity_id}"
                # Spread user attributes first so hardcoded values cannot be overridden
                attrs = {
                    **payload.attributes,
                    "unit_of_measurement": payload.unit,
                    "device_class": payload.device_class,
                    "friendly_name": payload.entity_id.replace("_", " ").title(),
                    "source": "nostr",
                }
                await self._ha.set_state(
                    entity_id=entity_id,
                    state=str(payload.value),
                    attributes=attrs,
                )
                logger.info("Updated %s = %s%s", entity_id, payload.value, payload.unit)

            case BinarySensorPayload():
                entity_id = f"binary_sensor.{self._prefix}_{payload.entity_id}"
                attrs = {
                    **payload.attributes,
                    "device_class": payload.device_class,
                    "friendly_name": payload.entity_id.replace("_", " ").title(),
                    "source": "nostr",
                }
                await self._ha.set_state(
                    entity_id=entity_id,
                    state="on" if payload.state else "off",
                    attributes=attrs,
                )
                logger.info("Updated %s = %s", entity_id, "on" if payload.state else "off")

            case NotificationPayload():
                await self._ha.fire_event(
                    event_type=f"{self._prefix}_notification",
                    data={
                        "title": payload.title,
                        "message": payload.message,
                        "severity": payload.severity,
                    },
                )
                logger.info("Fired notification: [%s] %s", payload.severity, payload.title or payload.message[:50])

    def _get_d_tag(self, event: Event) -> str | None:
        """Extract the 'd' tag value from a NOSTR event."""
        for tag in event.tags().to_vec():
            tag_vec = tag.as_vec()
            if len(tag_vec) >= 2 and tag_vec[0] == "d":
                return tag_vec[1]
        return None
