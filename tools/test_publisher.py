#!/usr/bin/env python3
"""
Test publisher — generates sample NOSTR events for end-to-end testing.

Usage:
    python test_publisher.py --bridge-pubkey <npub_or_hex> [--relay wss://relay.damus.io]

On first run with --generate-keys, it creates a keypair and prints the nsec/npub.
You then put the npub into the bridge's config as publisher_public_key.
"""

import argparse
import asyncio
import json
import random
import time

from nostr_sdk import (
    Client,
    EventBuilder,
    Keys,
    Kind,
    Nip44Version,
    NostrSigner,
    PublicKey,
    RelayUrl,
    Tag,
    nip44_encrypt,
)


def build_sensor_payload() -> dict:
    return {
        "type": "sensor",
        "entity_id": "outdoor_temperature",
        "value": round(random.uniform(60.0, 95.0), 1),
        "unit": "\u00b0F",
        "device_class": "temperature",
        "attributes": {"location": "backyard"},
    }


def build_binary_sensor_payload() -> dict:
    return {
        "type": "binary_sensor",
        "entity_id": "front_door",
        "state": random.choice([True, False]),
        "device_class": "door",
        "attributes": {"battery": random.randint(50, 100)},
    }


def build_notification_payload() -> dict:
    messages = [
        ("Motion Detected", "Camera 2 detected motion at driveway", "warning"),
        ("Low Battery", "Front door sensor battery at 15%", "info"),
        ("Smoke Alarm", "Kitchen smoke detector triggered", "critical"),
    ]
    title, message, severity = random.choice(messages)
    return {
        "type": "notification",
        "title": title,
        "message": message,
        "severity": severity,
    }


PAYLOAD_BUILDERS = [
    build_sensor_payload,
    build_binary_sensor_payload,
    build_notification_payload,
]


async def publish_events(
    publisher_keys: Keys,
    bridge_pubkey: PublicKey,
    relay_url: str,
    count: int,
    interval: float,
) -> None:
    # nostr-sdk requires the event loop to be registered for uniffi async
    from nostr_sdk import init_logger, LogLevel
    try:
        init_logger(LogLevel.INFO)
    except Exception:
        pass

    signer = NostrSigner.keys(publisher_keys)
    client = Client(signer)
    await client.add_relay(RelayUrl.parse(relay_url))
    await client.connect()
    print(f"Connected to {relay_url}")
    print(f"Publisher npub: {publisher_keys.public_key().to_bech32()}")
    print(f"Bridge npub:    {bridge_pubkey.to_bech32()}")
    print(f"Publishing {count} events every {interval}s...\n")

    for i in range(count):
        builder = random.choice(PAYLOAD_BUILDERS)
        payload = builder()
        plaintext = json.dumps(payload)

        # NIP-44 encrypt for the bridge's public key
        encrypted = nip44_encrypt(publisher_keys.secret_key(), bridge_pubkey, plaintext, Nip44Version.V2)

        # Build a kind 30078 replaceable event with d-tag = entity_id (if applicable)
        d_tag = payload.get("entity_id", f"notification_{int(time.time())}")
        event_builder = (
            EventBuilder(Kind(30078), encrypted)
            .tags([Tag.identifier(d_tag)])
        )

        output = await client.send_event_builder(event_builder)
        print(f"[{i+1}/{count}] Published {payload['type']:15s} | entity={d_tag:25s} | id={output.id.to_hex()[:12]}")

        if i < count - 1:
            await asyncio.sleep(interval)

    await client.disconnect()
    print("\nDone!")


def main() -> None:
    parser = argparse.ArgumentParser(description="NOSTR-HA Bridge test publisher")
    parser.add_argument("--bridge-pubkey", required=False, help="Bridge's npub or hex pubkey")
    parser.add_argument("--relay", default="wss://relay.damus.io", help="Relay URL")
    parser.add_argument("--count", type=int, default=5, help="Number of events to publish")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between events")
    parser.add_argument("--generate-keys", action="store_true", help="Generate and print a new keypair, then exit")
    parser.add_argument("--publisher-nsec", help="Use this nsec as the publisher key (otherwise generates a new one)")
    args = parser.parse_args()

    if args.generate_keys:
        keys = Keys.generate()
        print(f"nsec (private): {keys.secret_key().to_bech32()}")
        print(f"npub (public):  {keys.public_key().to_bech32()}")
        print(f"\nPut the npub into the bridge config as 'publisher_public_key'.")
        print(f"Keep the nsec secret — use it with --publisher-nsec to publish test events.")
        return

    if not args.bridge_pubkey:
        parser.error("--bridge-pubkey is required (or use --generate-keys)")

    if args.publisher_nsec:
        publisher_keys = Keys.parse(args.publisher_nsec)
    else:
        publisher_keys = Keys.generate()
        print(f"Generated ephemeral publisher key: {publisher_keys.public_key().to_bech32()}")
        print("(Use --publisher-nsec to reuse a key across runs)\n")

    bridge_pubkey = PublicKey.parse(args.bridge_pubkey)

    asyncio.run(publish_events(
        publisher_keys=publisher_keys,
        bridge_pubkey=bridge_pubkey,
        relay_url=args.relay,
        count=args.count,
        interval=args.interval,
    ))


if __name__ == "__main__":
    main()
