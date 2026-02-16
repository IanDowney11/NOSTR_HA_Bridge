#!/bin/bash
# ==============================================================================
# NOSTR-HA Bridge - Startup Script
# ==============================================================================
# Starts as root to read HA-mounted /data, then drops to non-root user.

echo "Starting NOSTR-HA Bridge..."

# Ensure the non-root user can read HA-mounted config
if [ -d /data ]; then
    chmod -R o+r /data
fi

cd /app
exec gosu bridge python3 -m src.main
