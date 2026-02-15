#!/bin/bash
# ==============================================================================
# NOSTR-HA Bridge - Startup Script
# ==============================================================================

echo "Starting NOSTR-HA Bridge..."

cd /app
exec python3 -m src.main
