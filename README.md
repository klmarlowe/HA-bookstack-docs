# HA BookStack Docs

Automatically generates and maintains documentation for your Home Assistant setup in [BookStack](https://www.bookstackapp.com/). Pulls live data from your HA instance via the REST API and publishes structured, styled pages that stay current as your system evolves.

## What It Generates

| Page | Contents |
|------|----------|
| **Quick Reference Guide** | URLs, entity domain counts, critical integrations, common tasks |
| **System Overview** | HA version, entity statistics, architecture, active integrations |
| **Entity Inventory** | All entities organized by domain with state and integration source |
| **Integration Quirks & Solutions** | Known issues and workarounds (configured in `config.yaml`) |
| **Critical Automations** | All automations with state and last-triggered time |
| **Notes** | Manually maintained page — never overwritten by the script |

Pages tagged `manual` in BookStack are always skipped. The Notes page is created with this tag automatically.

---

## Strongly Recommended: Use an LLM to Build Your Config

The `config.yaml` file is what makes this tool genuinely useful for your specific setup — not just a generic entity dump. It's where you document your integration quirks, network architecture, household members, coordinator details, and custom notes. Filling it in by hand works, but an LLM with access to your HA instance can do it in seconds.

**If you have Claude (or another LLM) connected to Home Assistant via MCP**, ask it to generate your `config.yaml` from scratch. It can:

- Inspect your full entity list and infer which integrations you're running
- Pre-populate the `quirks` section with known issues for those integrations
- Fill in coordinator hardware, network details, and exclusion patterns
- Identify unavailable or problematic devices worth flagging

Example prompt to get started:

> "Look at my Home Assistant entities and generate a config.yaml for the HA BookStack Docs script. Include a quirks section for each major integration I'm running, document my Zigbee and Z-Wave coordinators, and add exclusion patterns for noisy sensor entities."

The HA MCP integration (available via the Home Assistant Community Store or directly from Nabu Casa) gives any MCP-capable LLM read/write access to your HA instance. Claude Desktop, for example, can connect to HA via MCP and handle this config generation interactively — iterating with you on quirks, asking about devices it's uncertain about, and producing a config that reflects your actual setup rather than a generic template.

This step transforms the output from "automated entity list" to "living documentation of how your specific system works."

---

## Prerequisites

### 1. Home Assistant

Any recent version of Home Assistant OS, Container, or Supervised. You'll need a Long-Lived Access Token (created under your HA user profile).

### 2. BookStack

BookStack is a self-hosted wiki platform. You need a running BookStack instance before this script will do anything useful. There are two practical ways to run it alongside HA:

#### Option A — BookStack as a Home Assistant Add-on (easiest)

The [BookStack add-on](https://github.com/hassio-addons/addon-bookstack) is available in the Home Assistant Community Add-ons repository (HACS not required for add-ons).

1. In HA, go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu → **Repositories** → add:
   ```
   https://github.com/hassio-addons/repository
   ```
3. Search for **BookStack** and install it
4. Configure the add-on (set an admin email/password), then start it
5. BookStack will be available at `http://YOUR_HA_IP:PORT` (default port is usually 6875 — check the add-on's "Info" tab)

#### Option B — Standalone Docker container

For more control or if you prefer BookStack separate from HA:

```bash
docker run -d \
  --name=bookstack \
  -e PUID=1000 \
  -e PGID=1000 \
  -e APP_URL=http://YOUR_HOST_IP:6875 \
  -e DB_HOST=bookstack_db \
  -e DB_DATABASE=bookstackapp \
  -e DB_USERNAME=bookstack \
  -e DB_PASSWORD=yourdbpassword \
  -p 6875:80 \
  -v /path/to/bookstack/data:/config \
  --restart unless-stopped \
  lscr.io/linuxserver/bookstack
```

See the [LinuxServer BookStack image docs](https://docs.linuxserver.io/images/docker-bookstack/) for the full docker-compose setup including the required MariaDB container.

#### Getting a BookStack API Token

Once BookStack is running:

1. Log in as your admin user
2. Click your avatar → **Edit Profile**
3. Scroll to **API Tokens** → **Create Token**
4. Copy the Token ID and Token Secret — you'll need both in `config.yaml`

---

## Installation

### Python requirements

```bash
pip install requests pyyaml --break-system-packages
```

Or from the included file:

```bash
pip install -r requirements.txt --break-system-packages
```

Python 3.10+ recommended.

### Script installation

Copy the scripts to your HA config directory:

```bash
mkdir -p /config/scripts/ha_docs
cp ha_docs_production.py verify_setup.py config.yaml /config/scripts/ha_docs/
```

You can use the HA **File Editor** add-on, SSH, or Samba share to place files in `/config`.

### Add the shell command to `configuration.yaml`

```yaml
shell_command:
  update_ha_docs: "python3 /config/scripts/ha_docs/ha_docs_production.py --config /config/scripts/ha_docs/config.yaml"
```

Reload HA configuration, then test via **Developer Tools → Actions → shell_command.update_ha_docs**.

---

## Configuration

Copy the example config and fill in your details:

```bash
cp config.yaml.example config.yaml
chmod 600 config.yaml
```

### Required fields

```yaml
bookstack:
  url: "http://YOUR_BOOKSTACK_IP:PORT/"
  token_id: "YOUR_TOKEN_ID"
  token_secret: "YOUR_TOKEN_SECRET"

homeassistant:
  url: "http://homeassistant.local:8123"
  token: "YOUR_LONG_LIVED_ACCESS_TOKEN"
```

### Documenting your quirks

The `quirks` section is where most of the value comes from — a structured record of known issues and workarounds for your specific integrations:

```yaml
quirks:
  - integration: "Bond"
    severity: "medium"
    title: "RF devices lose state when controlled via physical remote"
    description: |
      Bond uses one-way RF. HA sends commands but cannot detect physical
      remote button presses, causing state drift over time.
    affected_devices:
      - "Living Room Fan (fan.living_room)"
      - "Bedroom Fan (fan.bedroom)"
    workaround: |
      Daily 4 AM automation resets all Bond device states.
      Long-term fix: install inline switches (Sonoff ZBMINIR2 in detached
      relay mode) to route physical presses through HA.
    notes: "Inline switch solution prevents drift entirely once deployed"
```

Severity levels: `low`, `medium`, `high`, `critical`

See `config.yaml.example` for the full list of available fields.

---

## Usage

### Verify your setup first

```bash
python3 /config/scripts/ha_docs/verify_setup.py
```

### Test mode — no changes to BookStack

```bash
python3 /config/scripts/ha_docs/ha_docs_production.py \
  --config /config/scripts/ha_docs/config.yaml \
  --test
```

### Generate and publish

```bash
python3 /config/scripts/ha_docs/ha_docs_production.py \
  --config /config/scripts/ha_docs/config.yaml
```

### Disable HTML styling

```bash
python3 /config/scripts/ha_docs/ha_docs_production.py \
  --config /config/scripts/ha_docs/config.yaml \
  --no-style
```

---

## Scheduled Updates

Add an HA automation to keep docs current automatically:

```yaml
automation:
  - alias: "Update BookStack Documentation Weekly"
    trigger:
      - platform: time
        at: "03:00:00"
        weekday: sun
    action:
      - action: shell_command.update_ha_docs
```

---

## BookStack Styling (Optional)

The script generates HTML-enhanced markdown that renders with styled tables, domain badges, status indicators, and callout boxes when you install the included CSS.

1. In BookStack, go to **Settings → Customization → Custom HTML Head Content**
2. Paste the contents of `bookstack_custom_html_head_content.txt`
3. Save and hard-refresh your browser

The script works without this — use `--no-style` (or `styled_output: false` in config) for plain markdown output.

---

## Protecting Manual Pages

Any BookStack page tagged `manual` will never be overwritten by the script. The Notes page is created with this tag automatically. To protect any other page, add the `manual` tag to it directly in BookStack.

---

## Integration Detection

The script infers which integration manages each entity using entity ID pattern matching, since the HA entity registry is not accessible via the REST API. It covers the most common integrations out of the box: Zigbee2MQTT, Z-Wave JS, Bond, Ring, SimpliSafe, Ecobee, LG ThinQ, ESPHome, Roborock, TP-Link Deco, and more.

Entities from integrations not covered will show as `Unknown` in the Entity Inventory. See `_build_integration_map()` in the script to add patterns for your setup.

---

## File Reference

| File | Purpose |
|------|---------|
| `ha_docs_production.py` | Main script |
| `config.yaml` | Your personal configuration — **do not commit** |
| `config.yaml.example` | Template for new users |
| `verify_setup.py` | Pre-flight connectivity and dependency check |
| `bookstack_custom_html_head_content.txt` | Optional BookStack CSS |
| `requirements.txt` | Python dependencies |

---

## Contributing

Common additions:

- New document types (Zigbee mesh topology, battery level inventory, etc.)
- Additional integration patterns in `_build_integration_map()`
- Quirk entries for integrations you've encountered issues with

Pull requests welcome. **Remove any personal tokens, IP addresses, or device names before sharing your `config.yaml`.**

The `config.yaml.example` in this repo is the right starting point — it contains no real credentials or network details.
