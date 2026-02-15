# Changelog

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
