#!/usr/bin/with-contenv bashio
# ==============================================================================
# NOSTR-HA Bridge - Startup Script
# ==============================================================================

bashio::log.info "Starting NOSTR-HA Bridge..."

cd /app
exec python3 -m src.main
