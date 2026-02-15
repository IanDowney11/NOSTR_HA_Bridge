"""Relay manager — subscribes to NOSTR relays and emits decrypted events."""

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import timedelta

from nostr_sdk import (
    Client,
    Event,
    Filter,
    HandleNotification,
    Kind,
    PublicKey,
    RelayMessage,
    RelayUrl,
    Timestamp,
)

from .nip44_crypto import Nip44Crypto

logger = logging.getLogger(__name__)

# Type alias for the callback that receives decrypted JSON strings
EventCallback = Callable[[str, Event], Awaitable[None]]


class NostrEventHandler(HandleNotification):
    """nostr-sdk notification handler that decrypts and forwards events."""

    def __init__(self, crypto: Nip44Crypto, callback: EventCallback, seen: OrderedDict[str, None]):
        self._crypto = crypto
        self._callback = callback
        self._seen = seen

    async def handle(self, relay_url: str, subscription_id: str, event: Event) -> None:
        event_id = event.id().to_hex()

        # Deduplicate across relays
        if event_id in self._seen:
            return
        self._seen[event_id] = None

        # Verify the event is from the expected publisher
        if event.author().to_hex() != self._crypto.publisher_public_key.to_hex():
            logger.debug("Ignoring event from unknown author: %s", event.author().to_bech32())
            return

        try:
            plaintext = self._crypto.decrypt(event.content())
        except Exception as e:
            logger.debug("Could not decrypt event %s from %s: %s", event_id[:12], relay_url, e)
            return

        logger.info("Decrypted event %s from %s", event_id[:12], relay_url)
        await self._callback(plaintext, event)

    async def handle_msg(self, relay_url: str, msg: RelayMessage) -> None:
        # We only care about event notifications, not relay-level messages
        pass


class RelayManager:
    """Manages connections to multiple NOSTR relays and event subscriptions."""

    def __init__(
        self,
        relays: list[str],
        event_kinds: list[int],
        crypto: Nip44Crypto,
        callback: EventCallback,
    ):
        self._relays = relays
        self._event_kinds = event_kinds
        self._crypto = crypto
        self._callback = callback
        self._client: Client | None = None
        self._seen: OrderedDict[str, None] = OrderedDict()
        # Cap the seen-set to prevent unbounded memory growth
        self._max_seen = 10_000

    async def start(self) -> None:
        """Connect to relays and start listening for events."""
        self._client = Client()

        for relay_url in self._relays:
            await self._client.add_relay(RelayUrl.parse(relay_url))
            logger.info("Added relay: %s", relay_url)

        await self._client.connect()
        logger.info("Connected to %d relay(s)", len(self._relays))

        # Build subscription filter
        kinds = [Kind(k) for k in self._event_kinds]
        sub_filter = (
            Filter()
            .kinds(kinds)
            .author(self._crypto.publisher_public_key)
            .since(Timestamp.now())
        )

        await self._client.subscribe(sub_filter, None)
        logger.info("Subscribed to kinds %s from publisher %s",
                     self._event_kinds,
                     self._crypto.publisher_public_key.to_bech32())

        # Start the notification handler
        handler = NostrEventHandler(self._crypto, self._callback, self._seen)
        await self._client.handle_notifications(handler)

    async def fetch_latest(self) -> None:
        """Poll relays for the latest events (fallback/catchup)."""
        if not self._client:
            return

        kinds = [Kind(k) for k in self._event_kinds]
        fetch_filter = (
            Filter()
            .kinds(kinds)
            .author(self._crypto.publisher_public_key)
            .limit(500)
        )

        events = await self._client.fetch_events(fetch_filter, timedelta(seconds=10))

        for event in events.to_vec():
            event_id = event.id().to_hex()
            if event_id in self._seen:
                continue
            self._seen[event_id] = None

            try:
                plaintext = self._crypto.decrypt(event.content())
            except Exception as e:
                logger.debug("Could not decrypt fetched event %s: %s", event_id[:12], e)
                continue

            logger.info("Fetched & decrypted event %s", event_id[:12])
            await self._callback(plaintext, event)

        self._prune_seen()

    async def stop(self) -> None:
        """Disconnect from all relays."""
        if self._client:
            await self._client.disconnect()
            logger.info("Disconnected from all relays")

    def _prune_seen(self) -> None:
        """Prevent the seen-set from growing without bound (FIFO eviction)."""
        if len(self._seen) > self._max_seen:
            # Evict oldest entries first (FIFO order via OrderedDict)
            excess = len(self._seen) - (self._max_seen // 2)
            for _ in range(excess):
                self._seen.popitem(last=False)
