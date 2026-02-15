"""Home Assistant API client for creating/updating entities and firing events."""

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """Communicates with Home Assistant Core via the Supervisor REST API."""

    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json"

        self._session = aiohttp.ClientSession(headers=headers)

        # Verify connectivity
        try:
            async with self._session.get(f"{self._base_url}/api/") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info("Connected to Home Assistant: %s", data.get("message", "OK"))
                else:
                    logger.warning("HA API returned status %d — entities may not update", resp.status)
        except aiohttp.ClientError:
            logger.warning("Cannot reach Home Assistant API at %s — will retry on first state update", self._base_url)

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, Any] | None = None) -> bool:
        """Create or update an entity's state in Home Assistant.

        Uses POST /api/states/<entity_id> which creates the entity if it doesn't exist.
        """
        if not self._session:
            logger.error("HA client not started — cannot set state for %s", entity_id)
            return False

        url = f"{self._base_url}/api/states/{entity_id}"
        payload: dict[str, Any] = {"state": state}
        if attributes:
            payload["attributes"] = attributes

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    return True
                body = await resp.text()
                logger.error("Failed to set state for %s: HTTP %d — %s", entity_id, resp.status, body)
                return False
        except aiohttp.ClientError:
            logger.exception("Network error setting state for %s", entity_id)
            return False

    async def fire_event(self, event_type: str, data: dict[str, Any] | None = None) -> bool:
        """Fire a custom event in Home Assistant.

        Uses POST /api/events/<event_type>.
        """
        if not self._session:
            logger.error("HA client not started — cannot fire event %s", event_type)
            return False

        url = f"{self._base_url}/api/events/{event_type}"

        try:
            async with self._session.post(url, json=data or {}) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.error("Failed to fire event %s: HTTP %d — %s", event_type, resp.status, body)
                return False
        except aiohttp.ClientError:
            logger.exception("Network error firing event %s", event_type)
            return False
