# NOSTR-HA Bridge

A Home Assistant add-on that bridges encrypted [NOSTR](https://nostr.com/) events into Home Assistant entities. Subscribe to any NOSTR relay, decrypt NIP-44 encrypted payloads, and automatically create sensors, binary sensors, and notifications in your smart home.

## Features

- **Real-time WebSocket** subscriptions to NOSTR relays with automatic reconnection
- **NIP-44 v2 encryption** (XChaCha20-Poly1305) for private data transfer
- **Kind 30078** parameterized replaceable events (state is always the latest value)
- **Automatic entity creation** — sensors, binary sensors, and notifications appear in HA with no YAML config
- **Fallback polling** catches any events missed by the WebSocket listener
- **Pluggable architecture** — add custom handlers for app-specific data formats

## How It Works

```
Your App ──NIP-44 encrypt──▶ NOSTR Relay ──▶ NOSTR-HA Bridge ──▶ Home Assistant
              kind 30078         wss://            decrypt           REST API
```

1. A publisher app encrypts JSON data with NIP-44 and publishes it as a kind 30078 event to NOSTR relays
2. The bridge subscribes to those relays, filters for events from a specific publisher public key
3. Events are decrypted using the shared key pair and routed based on their content
4. Home Assistant entities are created/updated via the REST API

## Installation

### As a Home Assistant Add-on

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**
2. Click the three-dot menu (top right) and select **Repositories**
3. Add this repository URL:
   ```
   https://github.com/IanDowney11/NOSTR_HA_Bridge
   ```
4. Find **NOSTR Bridge** in the store and click **Install**
5. Go to the **Configuration** tab and fill in your keys and relays (see [Configuration](#configuration))
6. Start the add-on

### Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example config:
   ```bash
   cp options.local.example.json options.local.json
   ```
4. Edit `options.local.json` with your keys and relay URLs
5. Set environment variables for your HA instance:
   ```bash
   # Linux/macOS
   export HA_BASE_URL="http://your-ha-ip:8123"
   export SUPERVISOR_TOKEN="your-long-lived-access-token"

   # Windows PowerShell
   $env:HA_BASE_URL = "http://your-ha-ip:8123"
   $env:SUPERVISOR_TOKEN = "your-long-lived-access-token"
   ```
6. Run the bridge:
   ```bash
   python -m src.main
   ```

## Configuration

| Option | Description |
|--------|-------------|
| `nostr_private_key` | Your NOSTR private key (nsec or hex). Used to decrypt incoming events. |
| `publisher_public_key` | The public key (npub or hex) of the account publishing events. The bridge only processes events from this author. |
| `relays` | List of NOSTR relay WebSocket URLs (e.g. `wss://relay.damus.io`) |
| `event_kinds` | NOSTR event kinds to subscribe to (default: `[30078]`) |
| `poll_fallback_interval` | Seconds between fallback polls (default: `300`) |
| `entity_prefix` | Prefix for HA entity IDs (default: `nostr`) |
| `log_level` | Logging level: `debug`, `info`, `warning`, or `error` |

### Key Setup

The bridge uses NIP-44 encryption, which requires a shared secret derived from two keypairs:

- **Reading your own data**: Use the same keypair for both `nostr_private_key` and `publisher_public_key`. Your app encrypts to itself, and the bridge (with the same private key) can decrypt.
- **Reading someone else's data**: The publisher encrypts to your public key. You configure their public key as `publisher_public_key` and your own private key as `nostr_private_key`.

To generate a new keypair for testing:
```bash
python tools/test_publisher.py --generate-keys
```

## Publishing Events

### Standard Payload Format

The bridge supports three entity types out of the box. Publish a kind 30078 event with NIP-44 encrypted JSON in one of these formats:

#### Sensor

```json
{
  "type": "sensor",
  "entity_id": "outdoor_temperature",
  "value": 72.5,
  "unit": "°F",
  "device_class": "temperature",
  "attributes": {
    "location": "backyard"
  }
}
```

Creates `sensor.nostr_outdoor_temperature` in HA.

#### Binary Sensor

```json
{
  "type": "binary_sensor",
  "entity_id": "front_door",
  "state": true,
  "device_class": "door",
  "attributes": {
    "battery": 85
  }
}
```

Creates `binary_sensor.nostr_front_door` in HA (state: on/off).

#### Notification

```json
{
  "type": "notification",
  "title": "Motion Detected",
  "message": "Camera 2 detected motion at driveway",
  "severity": "warning"
}
```

Fires a `nostr_notification` event in HA that you can use in automations.

### D-Tags

Events should include a NOSTR `d` tag to make them parameterized replaceable (kind 30078). This means only the latest value for each d-tag is stored on relays:

- For sensors/binary sensors, use the `entity_id` as the d-tag
- For notifications, use a unique identifier

### Test Publisher

A test publisher is included for end-to-end testing:

```bash
# Generate keys
python tools/test_publisher.py --generate-keys

# Publish test events
python tools/test_publisher.py \
  --publisher-nsec nsec1... \
  --bridge-pubkey npub1... \
  --relay wss://relay.damus.io \
  --count 5
```

## Extending the Bridge

The bridge has a pluggable routing architecture. Events are routed based on their `d` tag prefix:

```
NOSTR Event
  │
  ├─ d-tag starts with "mmp:" → MealPlannerHandler (built-in)
  ├─ d-tag starts with "xyz:" → Your custom handler
  │
  └─ default → Standard payload router (sensor / binary_sensor / notification)
```

### Adding a Custom Handler

1. **Create a handler** in `src/` (e.g., `src/my_app.py`):

```python
class MyAppHandler:
    def __init__(self, ha_client, entity_prefix):
        self._ha = ha_client
        self._prefix = entity_prefix

    async def handle_event(self, data: dict, d_tag: str) -> None:
        # Parse your app's data and create HA entities
        await self._ha.set_state(
            entity_id=f"sensor.{self._prefix}_my_value",
            state=str(data["value"]),
            attributes={"friendly_name": "My Value", "source": "nostr"},
        )
```

2. **Register it** in `src/event_router.py`:

```python
from .my_app import MyAppHandler

class EventRouter:
    def __init__(self, ha_client, entity_prefix="nostr"):
        # ... existing code ...
        self._my_app = MyAppHandler(ha_client, entity_prefix)

    async def handle_event(self, plaintext, event):
        d_tag = self._get_d_tag(event)

        if d_tag and d_tag.startswith("myapp:"):
            raw = json.loads(plaintext)
            await self._my_app.handle_event(raw, d_tag)
            return

        # ... rest of existing routing ...
```

### Built-in: MyMealPlanner Integration

The bridge includes a handler for [MyMealPlanner](https://github.com/IanDowney11/MyMealPlanner) events (d-tag prefix `mmp:`). It creates a `sensor.nostr_todays_meal` entity showing today's planned meal with title, image, rating, and tags.

## Architecture

```
src/
├── main.py           # Async entrypoint, wires components, runs event loop
├── config.py         # Loads config from HA add-on options or local JSON file
├── relay_manager.py  # WebSocket connections, subscriptions, event deduplication
├── nip44_crypto.py   # NIP-44 v2 encrypt/decrypt (supports chunked format)
├── event_router.py   # Routes events by d-tag prefix or payload type
├── mealplanner.py    # MyMealPlanner custom handler
├── ha_client.py      # Home Assistant REST API client
└── models.py         # Pydantic models for sensor/binary_sensor/notification

tools/
└── test_publisher.py # CLI tool for publishing test events
```

## NOSTR Protocol Details

- **Event Kind**: 30078 (parameterized replaceable — latest event per d-tag wins)
- **Encryption**: NIP-44 v2 (XChaCha20-Poly1305 with HKDF key derivation)
- **D-Tags**: Used for entity identity and replaceable event semantics
- **Relay Protocol**: NIP-01 WebSocket subscriptions with real-time streaming

## Dashboard Example

Add a Markdown card to your HA dashboard to display data from the bridge:

```yaml
type: markdown
content: >-
  ## Today's Meal

  **{{ states('sensor.nostr_todays_meal') }}**

  {% if state_attr('sensor.nostr_todays_meal', 'entity_picture') %}
  <img src="{{ state_attr('sensor.nostr_todays_meal', 'entity_picture') }}"
  style="max-width:300px; border-radius:8px;" />
  {% endif %}
```

## License

This project is released into the public domain under the [Unlicense](LICENSE). Do whatever you want with it.
