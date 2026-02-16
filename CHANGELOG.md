# Changelog

## 0.5.2

- **Early logging init**: Configure logging before `load_config()` so startup errors (e.g. missing `/data/options.json`) include timestamps
- **Fix `/data` permission denied**: Container starts as root to chmod HA-mounted `/data`, then drops to non-root `bridge` user via `gosu`

## 0.5.0

### Security Hardening

- **Entity ID validation**: Reject payloads with entity IDs containing special characters (only `[a-z0-9_]` allowed, max 64 chars)
- **Image URL validation**: Only accept `http://` and `https://` schemes for `entity_picture` attributes
- **Non-root container**: Docker container now runs as a dedicated `bridge` user instead of root
- **Attribute spoofing prevention**: Hardcoded entity attributes (`friendly_name`, `source`) can no longer be overridden by publisher payloads
- **Log injection prevention**: Control characters stripped from decrypted content before logging
- **ws:// relay warning**: Unencrypted WebSocket relay URLs now produce a prominent warning at startup
- **Plan cache bounded**: Meal plan cache limited to a 30-day window around today to prevent memory exhaustion
- **FIFO deduplication**: Seen-event set now evicts oldest entries first (was random) using `OrderedDict`
- **`.dockerignore` added**: Prevents `options.local.json`, `.git/`, and other sensitive files from leaking into Docker image layers

## 0.4.1

- Fix `build.yaml` to use fully-qualified Docker Hub image references (HA Supervisor requires `registry/org/image` format)
- Restore `ARG BUILD_FROM` pattern in Dockerfile for proper HA builder integration

## 0.4.0

- Switch Docker base image from Alpine to Debian (`python:3.11-slim-bookworm`) to fix build hanging on aarch64 (nostr-sdk has no pre-built wheel for musl/Alpine)
- Pin `nostr-sdk==0.44.2` in requirements
- Remove bashio dependency from `run.sh`

## 0.3.0

- Fix Docker build for Alpine: use `apk` instead of `apt-get`, add build dependencies for native Python packages
- Add `build.yaml` with per-architecture base image mapping

## 0.2.0

- Fix Docker build for aarch64: add `build.yaml` and `.gitattributes` for correct base image selection and LF line endings

## 0.1.0

- Initial release
- Real-time WebSocket subscriptions to NOSTR relays
- NIP-44 v2 decryption of kind 30078 events
- Automatic creation of HA sensors, binary sensors, and notifications
- Fallback polling for missed events
- MyMealPlanner integration (d-tag prefix `mmp:`)
- Test publisher CLI tool
