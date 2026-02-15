"""NOSTR-HA Bridge — Main entry point."""

import asyncio
import logging
import signal
import sys

from .config import load_config
from .event_router import EventRouter
from .ha_client import HomeAssistantClient
from .nip44_crypto import Nip44Crypto
from .relay_manager import RelayManager

logger = logging.getLogger("nostr_ha_bridge")


async def run() -> None:
    # ── Load configuration ──────────────────────────────────────────────
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    logger.info("NOSTR-HA Bridge starting up")
    logger.info("Relays: %s", ", ".join(config.relays))
    logger.info("Entity prefix: %s", config.entity_prefix)

    # ── Initialize components ───────────────────────────────────────────
    crypto = Nip44Crypto(config.nostr_private_key, config.publisher_public_key)

    ha_client = HomeAssistantClient(config.ha_base_url, config.ha_token)
    await ha_client.start()

    router = EventRouter(ha_client, config.entity_prefix)

    relay_mgr = RelayManager(
        relays=config.relays,
        event_kinds=config.event_kinds,
        crypto=crypto,
        callback=router.handle_event,
    )

    # ── Graceful shutdown ───────────────────────────────────────────────
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # ── Start relay listener + poll fallback ────────────────────────────
    async def poll_loop() -> None:
        """Periodically fetch latest events as a fallback."""
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=config.poll_fallback_interval,
                )
                break  # shutdown_event was set
            except asyncio.TimeoutError:
                pass  # timeout elapsed — time to poll

            logger.debug("Running fallback poll")
            try:
                await relay_mgr.fetch_latest()
            except Exception:
                logger.exception("Error during fallback poll")

            # Check if the date has changed (for daily meal plan refresh)
            try:
                await router.refresh_daily()
            except Exception:
                logger.exception("Error during daily refresh")

    # Fetch latest on startup to hydrate existing state
    logger.info("Fetching latest events from relays to hydrate state...")

    listener_task = asyncio.create_task(relay_mgr.start(), name="relay_listener")
    poll_task = asyncio.create_task(poll_loop(), name="poll_fallback")

    # Give the listener a moment to connect, then do initial fetch
    await asyncio.sleep(3)
    try:
        await relay_mgr.fetch_latest()
    except Exception:
        logger.exception("Error during initial state hydration")

    logger.info("NOSTR-HA Bridge is running")

    # ── Wait for shutdown ───────────────────────────────────────────────
    await shutdown_event.wait()

    logger.info("Shutting down...")
    listener_task.cancel()
    poll_task.cancel()

    await relay_mgr.stop()
    await ha_client.stop()
    logger.info("NOSTR-HA Bridge stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
