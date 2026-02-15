"""Configuration loader for the NOSTR-HA Bridge add-on."""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

ADDON_OPTIONS_PATH = "/data/options.json"
LOCAL_OPTIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "options.local.json")


@dataclass
class BridgeConfig:
    nostr_private_key: str
    publisher_public_key: str
    relays: list[str]
    event_kinds: list[int] = field(default_factory=lambda: [30078])
    poll_fallback_interval: int = 300
    entity_prefix: str = "nostr"
    log_level: str = "info"

    # Runtime — injected by the HA supervisor environment
    ha_token: str = ""
    ha_base_url: str = "http://supervisor/core"

    def validate(self) -> None:
        if not self.nostr_private_key:
            raise ValueError("nostr_private_key is required")
        if not self.publisher_public_key:
            raise ValueError("publisher_public_key is required")
        if not self.relays:
            raise ValueError("At least one relay URL is required")
        for url in self.relays:
            if not url.startswith(("wss://", "ws://")):
                raise ValueError(f"Invalid relay URL (must start with wss:// or ws://): {url}")


def load_config() -> BridgeConfig:
    """Load config from the HA add-on options file, falling back to a local dev file."""
    options_path = Path(ADDON_OPTIONS_PATH)
    if not options_path.exists():
        options_path = Path(LOCAL_OPTIONS_PATH)
        if not options_path.exists():
            raise FileNotFoundError(
                f"No options file found at {ADDON_OPTIONS_PATH} or {LOCAL_OPTIONS_PATH}. "
                "Create options.local.json for local development."
            )
        logger.info("Using local dev config: %s", options_path)

    with open(options_path, "r") as f:
        raw = json.load(f)

    config = BridgeConfig(
        nostr_private_key=raw["nostr_private_key"],
        publisher_public_key=raw["publisher_public_key"],
        relays=raw.get("relays", ["wss://relay.damus.io"]),
        event_kinds=raw.get("event_kinds", [30078]),
        poll_fallback_interval=raw.get("poll_fallback_interval", 300),
        entity_prefix=raw.get("entity_prefix", "nostr"),
        log_level=raw.get("log_level", "info"),
    )

    # HA Supervisor injects this token for add-ons with homeassistant_api: true
    config.ha_token = os.environ.get("SUPERVISOR_TOKEN", "")
    config.ha_base_url = os.environ.get("HA_BASE_URL", "http://supervisor/core")

    config.validate()
    return config
