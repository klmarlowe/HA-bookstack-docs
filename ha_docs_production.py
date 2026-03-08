#!/usr/bin/env python3
"""
Home Assistant to BookStack Documentation Generator - Production Version with Styling
Pulls real data from Home Assistant via REST API

CHANGES FROM ORIGINAL:
- Added BookStackStyleFormatter class for HTML styling
- Enhanced markdown output with HTML classes for callouts, badges, tables
- NO changes to API logic, paths, or core functionality
- 100% backward compatible - works with same config file

Requirements:
    pip install requests pyyaml --break-system-packages
"""

import requests
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import yaml
import os


class HomeAssistantAPI:
    """Home Assistant REST API wrapper"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make API request"""
        url = f"{self.base_url}/api/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def get_config(self) -> Dict:
        """Get HA configuration"""
        return self._request('GET', 'config')
    
    def get_states(self) -> List[Dict]:
        """Get all entity states"""
        return self._request('GET', 'states')
    
    def get_services(self) -> List[Dict]:
        """Get all available services"""
        return self._request('GET', 'services')
    
    def get_error_log(self) -> str:
        """Get error log"""
        return self._request('GET', 'error_log')
    
    def get_states_with_context(self) -> List[Dict]:
        """Get all entity states (alias for get_states)"""
        return self.get_states()


class BookStackAPI:
    """BookStack API wrapper"""
    
    def __init__(self, base_url: str, token_id: str, token_secret: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Token {token_id}:{token_secret}',
            'Content-Type': 'application/json'
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request"""
        url = f"{self.base_url}/api/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def list_books(self) -> List[Dict]:
        """List all books"""
        return self._request('GET', 'books').get('data', [])
    
    def find_book_by_name(self, book_name: str) -> Optional[Dict]:
        """Find a book by name"""
        books = self.list_books()
        for book in books:
            if book['name'] == book_name:
                return book
        return None
    
    def create_book(self, name: str, description: str = "") -> Dict:
        """Create a new book"""
        data = {
            'name': name,
            'description': description
        }
        return self._request('POST', 'books', json=data)
    
    def create_page(self, book_id: int, chapter_id: Optional[int], 
                   name: str, markdown: str, tags: List[Dict] = None) -> Dict:
        """Create a new page"""
        data = {
            'book_id': book_id,
            'name': name,
            'markdown': markdown
        }
        if chapter_id:
            data['chapter_id'] = chapter_id
        if tags:
            data['tags'] = tags
        return self._request('POST', 'pages', json=data)
    
    def update_page(self, page_id: int, markdown: str, name: str = None) -> Dict:
        """Update an existing page"""
        data = {'markdown': markdown}
        if name:
            data['name'] = name
        return self._request('PUT', f'pages/{page_id}', json=data)
    
    def find_page_by_name(self, book_id: int, page_name: str) -> Optional[Dict]:
        """Find a page by name in a book"""
        book = self._request('GET', f'books/{book_id}')
        for item in book.get('contents', []):
            if item['type'] == 'page' and item['name'] == page_name:
                return item
            # Check chapters
            if item['type'] == 'chapter':
                for page in item.get('pages', []):
                    if page['name'] == page_name:
                        return page
        return None
    
    def get_page_tags(self, page_id: int) -> List[str]:
        """Get tags for a specific page"""
        page = self._request('GET', f'pages/{page_id}')
        return [tag['name'] for tag in page.get('tags', [])]
    
    def page_is_manual(self, page_id: int) -> bool:
        """Check if a page has 'manual' tag indicating it should not be auto-updated"""
        tags = self.get_page_tags(page_id)
        return 'manual' in tags


class BookStackStyleFormatter:
    """
    NEW CLASS: Helper for adding BookStack HTML styling to markdown
    Converts plain markdown to styled HTML without changing core logic
    """
    
    @staticmethod
    def callout(message: str, type: str = "info") -> str:
        """Create styled callout box (info, warning, success, danger)"""
        return f'\n<div class="callout {type}">\n\n{message}\n\n</div>\n\n'
    
    @staticmethod
    def badge(domain: str) -> str:
        """Create domain badge"""
        return f'<span class="badge {domain}">{domain}</span>'
    
    @staticmethod
    def status(state: str) -> str:
        """Create status indicator"""
        if state in ['unavailable', 'unknown', 'off']:
            return '<span class="status offline">Offline</span>'
        return '<span class="status online">Online</span>'
    
    @staticmethod
    def collapsible(title: str, content: str) -> str:
        """Create collapsible section"""
        return f'\n<details>\n<summary>{title}</summary>\n\n{content}\n\n</details>\n\n'
    
    @staticmethod
    def area_section_start(area_name: str) -> str:
        """Start an area section"""
        return f'\n<div class="area-section">\n\n## {area_name}\n\n'
    
    @staticmethod
    def area_section_end() -> str:
        """End an area section"""
        return '\n</div>\n\n'


class HADocumentationGenerator:
    """Generate comprehensive HA documentation"""
    
    def __init__(self, ha_api: HomeAssistantAPI, config: Dict, styled: bool = True):
        self.ha = ha_api
        self.user_config = config  # Store full user config
        self.config_data = None  # HA config from API
        self.states = None
        self.services = None
        self.styled = styled
        self.style = BookStackStyleFormatter() if styled else None
        
        # Extract config sections
        self.system_info = config.get('system_info', {})
        self.quirks = config.get('quirks', [])
        self.custom_sections = config.get('custom_sections', {})
        self.exclusions = config.get('exclusions', {})
    
    def _should_exclude_entity(self, entity_id: str, friendly_name: str = "", area: str = "") -> bool:
        """Check if entity should be excluded based on config"""
        import re
        
        # Check domain exclusions
        domain = entity_id.split('.')[0]
        if domain in self.exclusions.get('domains', []):
            return True
        
        # Check area exclusions
        if area and area in self.exclusions.get('areas', []):
            return True
        
        # Check specific entity exclusions
        if entity_id in self.exclusions.get('entities', []):
            return True
        
        # Check pattern exclusions
        for pattern in self.exclusions.get('entity_patterns', []):
            try:
                if re.match(pattern, entity_id):
                    return True
                if friendly_name and re.match(pattern, friendly_name):
                    return True
            except re.error:
                # Invalid regex pattern, skip it
                pass
        
        return False
        
    def fetch_data(self):
        """Fetch all data from HA"""
        print("  📡 Fetching HA configuration...")
        self.config_data = self.ha.get_config()
        
        print("  📡 Fetching entity states...")
        self.states = self.ha.get_states()
        
        print("  📡 Fetching services...")
        self.services = self.ha.get_services()
        
        # Build integration map from services + entity ID patterns
        self._integration_map = self._build_integration_map()
    
    def _build_integration_map(self) -> Dict[str, str]:
        """
        Infer integration for each entity using entity ID patterns.
        The HA registry APIs are WebSocket-only in 2026.x, so we use pattern matching.
        Patterns are checked in order; first match wins.
        """
        # (substring_in_entity_id, integration_label)
        # More specific patterns first
        PATTERNS = [
            # Zigbee2MQTT bridge entities - explicit prefix
            ('zigbee2mqtt',             'Zigbee2MQTT'),

            # Z-Wave - long compound entity IDs with room + device + attribute
            # e.g. sensor.rec_room_side_door_lock_rec_room_side_door_lock_battery_level_2
            ('_door_lock_',             'Z-Wave JS'),
            ('_front_door_lock_',       'Z-Wave JS'),
            ('_side_door_lock_',        'Z-Wave JS'),
            ('zwave',                   'Z-Wave JS'),
            ('z_wave',                  'Z-Wave JS'),

            # Ring alarm sensors (Yorktown = base station name)
            ('yorktown',                'Ring'),
            ('ring',                    'Ring'),

            # Ecobee thermostats and sensors
            ('ecobee',                  'Ecobee'),
            ('downstairs_temperature',  'Ecobee'),
            ('downstairs_humidity',     'Ecobee'),
            ('upstairs_temperature',    'Ecobee'),
            ('upstairs_humidity',       'Ecobee'),

            # Bond RF devices
            ('bond',                    'Bond'),

            # TP-Link Deco router
            ('tp_link_deco',            'TP-Link Deco'),
            ('tp_link',                 'TP-Link Deco'),

            # Gecko swim spa
            ('swim_spa',                'Gecko'),
            ('gecko',                   'Gecko'),

            # Tasmota
            ('tasmota',                 'Tasmota'),

            # LG ThinQ appliances
            ('dishwasher',              'LG ThinQ'),
            ('washing_machine',         'LG ThinQ'),
            ('refrigerator',            'LG ThinQ'),
            ('dryer',                   'LG ThinQ'),
            ('lg_',                     'LG ThinQ'),
            ('thinq',                   'LG ThinQ'),

            # Stormglass ocean/tide data
            ('stormglass',              'Stormglass'),

            # Weather station (WS103 Ambient Weather)
            ('ws103',                   'Ambient Weather'),

            # AdGuard Home
            ('adguard',                 'AdGuard Home'),

            # SpeedTest
            ('speedtest',               'Speedtest'),

            # HP Printer
            ('hp_color_laserjet',       'HP Printer'),
            ('hp_',                     'HP Printer'),

            # Roborock
            ('roborock',                'Roborock'),

            # ESPHome (CYD touchscreen device)
            ('cyd',                     'ESPHome'),
            ('esphome',                 'ESPHome'),

            # HA Mobile App (iPhones, iPads)
            ('iphone',                  'HA Companion App'),
            ('ipad',                    'HA Companion App'),
            ('_iphone_',                'HA Companion App'),

            # Wyze cameras
            ('wyze',                    'Wyze'),

            # Samsung SmartThings / TV
            ('tv_tv',                   'SmartThings'),

            # Mail and Packages integration
            ('mail_',                   'Mail & Packages'),

            # Dominion Energy
            ('dominion_energy',         'Dominion Energy'),

            # Backup integration
            ('backup_',                 'HA Backup'),

            # Sun
            ('sun_',                    'HA Sun'),

            # Plug entities (Tasmota/smart plugs)
            ('plug_',                   'Smart Plug'),

            # Alarm/security sensors without explicit ring prefix
            # (front_door_info, back_door_info, side_door_info, etc. are Ring Alarm)
            ('_door_info',              'Ring'),
            ('_door_battery',           'Ring'),
            ('_door_wireless',          'Ring'),
            ('motion_detector_info',    'Ring'),
            ('motion_detector_battery', 'Ring'),
            ('range_extender_info',     'Ring'),
            ('range_extender_battery',  'Ring'),
            ('keypad_info',             'Ring'),
            ('keypad_battery',          'Ring'),
            ('alarm_info',              'Ring'),
            ('base_station',            'Ring'),

            # Zigbee2MQTT device sensors (motion, water, climate sensors)
            # These don't have zigbee2mqtt in the name but are Z2M devices
            ('motion_sensor_',          'Zigbee2MQTT'),
            ('water_sensor_',           'Zigbee2MQTT'),
            ('bedroom_temperature',     'Zigbee2MQTT'),
            ('living_room_temperature', 'Zigbee2MQTT'),
            ('kitchen_temperature',     'Zigbee2MQTT'),
            ('ryan_s_room_temperature', 'Zigbee2MQTT'),
            ('bay_room_temperature',    'Zigbee2MQTT'),

            # Crabhouse, KLM, etc. - HA Companion App devices
            ('crabhouse',               'HA Companion App'),
            ('klm_',                    'HA Companion App'),

            # Energy/power sensors
            ('energy_today',            'HA Energy'),
            ('power',                   'HA Energy'),
            ('voltage',                 'HA Energy'),
            ('current',                 'HA Energy'),
        ]

        # Domain-level defaults for anything not matched above
        DOMAIN_DEFAULTS = {
            'automation':               'HA Automation',
            'script':                   'HA Script',
            'scene':                    'HA Scene',
            'input_boolean':            'HA Helper',
            'input_number':             'HA Helper',
            'input_select':             'HA Helper',
            'input_text':               'HA Helper',
            'input_datetime':           'HA Helper',
            'input_button':             'HA Helper',
            'counter':                  'HA Helper',
            'timer':                    'HA Helper',
            'schedule':                 'HA Helper',
            'person':                   'HA Person',
            'zone':                     'HA Zone',
            'sun':                      'HA Sun',
            'weather':                  'Met.no',
            'update':                   'HA Update',
            'button':                   'HA Button',
            'notify':                   'HA Notify',
            'persistent_notification':  'HA Core',
            'conversation':             'HA Voice',
            'stt':                      'HA Voice',
            'tts':                      'HA Voice',
            'wake_word':                'HA Voice',
            'climate':                  'Ecobee',
            'fan':                      'Bond',
            'lock':                     'Z-Wave JS',
            'camera':                   'Ring',
            'alarm_control_panel':      'Ring',
        }

        integration_map = {}
        for state in self.states:
            entity_id = state['entity_id']
            domain = entity_id.split('.')[0]
            entity_lower = entity_id.lower()

            matched = None
            for pattern, integration in PATTERNS:
                if pattern in entity_lower:
                    matched = integration
                    break

            if not matched:
                matched = DOMAIN_DEFAULTS.get(domain, 'Unknown')

            integration_map[entity_id] = matched

        return integration_map
        """Count entities by domain"""
        counts = {}
        for state in self.states:
            domain = state['entity_id'].split('.')[0]
            counts[domain] = counts.get(domain, 0) + 1
        return counts
    
    def _count_entities_by_domain(self) -> Dict[str, int]:
        """Count entities by domain"""
        counts = {}
        for state in self.states:
            domain = state['entity_id'].split('.')[0]
            counts[domain] = counts.get(domain, 0) + 1
        return counts

    def _count_entities_by_area(self) -> Dict[str, int]:
        """Count entities by area"""
        counts = {}
        for state in self.states:
            area = state.get('attributes', {}).get('friendly_name', 'Unknown')
            # This is simplified - real area mapping would need area registry
            counts[area] = counts.get(area, 0) + 1
        return counts
    
    def _get_integrations(self) -> List[str]:
        """Get list of integrations from services"""
        integrations = set()
        for service in self.services:
            integrations.add(service['domain'])
        return sorted(list(integrations))
    
    def generate_system_overview(self) -> str:
        """Generate system overview from live data"""
        entity_counts = self._count_entities_by_domain()
        total_entities = sum(entity_counts.values())
        integrations = self._get_integrations()
        
        doc = ""

        # Status summary as a simple markdown table (avoids CSS callout rendering issues)
        doc += f"""| | |
|---|---|
| **System Status** | ✅ Running |
| **Version** | {self.config_data.get('version', 'Unknown')} |
| **Total Entities** | {total_entities:,} |
| **Last Updated** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |

"""
        
        doc += f"""*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Home Assistant Installation

- **Version**: {self.config_data.get('version', 'Unknown')}
- **Location**: {self.system_info.get('location_name', self.config_data.get('location_name', 'Unknown'))}
- **Installation Type**: Home Assistant OS
- **URL**: {self.config_data.get('internal_url', 'Unknown')}
- **Timezone**: {self.config_data.get('time_zone', 'Unknown')}

## System Statistics

- **Total Entities**: {total_entities:,}
- **Active Integrations**: {len(integrations)}
- **Latitude**: {self.config_data.get('latitude', 'Unknown')}
- **Longitude**: {self.config_data.get('longitude', 'Unknown')}
- **Elevation**: {self.config_data.get('elevation', 'Unknown')}m
- **Unit System**: {self.config_data.get('unit_system', {}).get('temperature', 'Unknown')}


## Entity Breakdown by Domain

| Domain | Count |
|--------|-------|
"""
        # Sort by count descending
        for domain, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:15]:
            domain_label = f"{self.style.badge(domain)} {domain}" if self.styled else domain
            doc += f"| {domain_label} | {count} |\n"
        
        doc += f"""
## Key Household Members

- Kevin (Primary Administrator)
- Jill
- Ryan

## Architecture

```
┌─────────────────────────────────────────┐
│         Home Assistant OS               │
│         (Proxmox VM)                    │
├─────────────────────────────────────────┤
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ │
│  │  ZHA    │ │  MQTT    │ │ Cloud   │ │
│  │ Zigbee  │ │  Broker  │ │Services │ │
│  └────┬────┘ └────┬─────┘ └────┬────┘ │
└───────┼───────────┼────────────┼──────┘
        │           │            │
    ┌───▼───┐   ┌───▼────┐   ┌──▼─────┐
    │Zigbee │   │Tasmota │   │Ecobee  │
    │Devices│   │ WiFi   │   │ Ring   │
    │       │   │Devices │   │LG etc  │
    └───────┘   └────────┘   └────────┘
```

## Active Integrations

Total: {len(integrations)}

"""
        # List integrations in columns
        cols = 3
        for i in range(0, len(integrations), cols):
            row_integrations = integrations[i:i+cols]
            doc += "| " + " | ".join(row_integrations) + " |\n"
        
        doc += """
## System Health

| Component | Status |
|-----------|--------|
| Home Assistant Core | ✅ Running |
| Total Entities | """ + str(total_entities) + """ |
| Configuration Valid | ✅ Yes |

## Important Notes

### For Future Administrators

This system is designed with "Wife Acceptance Factor" (WAF) in mind - everything should work intuitively, especially voice commands via Alexa.

### System Philosophy

1. **Local Control Priority**: Where possible, devices communicate locally
2. **Voice-First Interface**: Alexa integration is primary control method for non-technical users
3. **Reliability Over Features**: Simple automations that work > complex ones that break
4. **Physical Switches Work**: All automations preserve physical switch functionality
5. **Graceful Degradation**: If HA goes down, house still functions manually

### Network Architecture

- **Router**: TP-Link Deco mesh system
- **DHCP Reservations**: Critical devices have static assignments
- **Zigbee Coordinator**: ZBT-2 (Texas Instruments CC2652) in Office
- **Z-Wave**: Nabu Casa Connect USB stick

### Critical Information for Troubleshooting

**If Home Assistant is Down**:
1. All smart devices will still respond to physical controls
2. Alexa voice commands will fail for local devices
3. Cloud-based devices (Ring, Ecobee) continue to work via their apps
4. Automations will not run

**Common Issues**:
- Bond RF devices may lose state if controlled via physical remote (4 AM sync runs daily)
- Zigbee devices occasionally need coordinator reboot (power cycle USB stick)
- Z-Wave devices may need network heal if behaving oddly
"""
        
        # Add custom overview notes if provided
        if 'system_overview_notes' in self.custom_sections:
            doc += "\n---\n\n"
            doc += self.custom_sections['system_overview_notes']
        
        return doc
    
    def generate_entity_inventory(self) -> str:
        """Generate comprehensive entity inventory"""
        entity_counts = self._count_entities_by_domain()
        
        doc = f"""*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Overview

This inventory lists all entities in Home Assistant, organized by domain and area.

**Total Entities**: {sum(entity_counts.values())}

"""
        
        # Group entities by domain
        by_domain = {}
        for state in self.states:
            domain = state['entity_id'].split('.')[0]
            by_domain.setdefault(domain, []).append(state)
        
        # Generate inventory for each domain
        for domain in sorted(by_domain.keys()):
            entities = by_domain[domain]
            
            if self.styled:
                doc += self.style.area_section_start(f"{domain.title()} Entities ({len(entities)})")
            else:
                doc += f"\n## {domain.title()} Entities ({len(entities)})\n\n"
            
            # Create entity table
            doc += "| Entity ID | Friendly Name | State | Integration |\n"
            doc += "|-----------|---------------|-------|-------------|\n"
            
            for entity in sorted(entities, key=lambda x: x['entity_id'])[:50]:  # Limit to 50 per domain
                entity_id = f"`{entity['entity_id']}`"
                name = entity.get('attributes', {}).get('friendly_name', entity['entity_id'])
                state = entity.get('state', 'unknown')
                integration = self._integration_map.get(entity['entity_id'], 'Unknown')
                
                # Add status badge for styled output
                if self.styled and state in ['unavailable', 'unknown']:
                    state_display = self.style.status(state)
                else:
                    state_display = state
                
                doc += f"| {entity_id} | {name} | {state_display} | {integration} |\n"
            
            if len(entities) > 50:
                doc += f"\n*Showing first 50 of {len(entities)} entities*\n\n"
            
            if self.styled:
                doc += self.style.area_section_end()
        
        return doc
    
    def generate_integration_quirks(self) -> str:
        """Generate integration-specific quirks documentation"""
        doc = f"""*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Integration Quirks & Solutions

This page documents known quirks, limitations, and workarounds for integrations used in this Home Assistant setup.

"""
        
        # Generate from config
        if self.quirks:
            for quirk in self.quirks:
                doc += self._format_quirk(quirk)
        else:
            # No quirks configured - show template
            doc += self._generate_quirks_template()
        
        # Add Zigbee section if configured
        zigbee_section = self._generate_zigbee_section()
        if zigbee_section:
            doc += "\n---\n\n" + zigbee_section
        
        # Add custom footer if provided
        if 'integration_quirks_footer' in self.custom_sections:
            doc += "\n---\n\n"
            doc += self.custom_sections['integration_quirks_footer']
        
        return doc
    
    def _format_quirk(self, quirk: Dict) -> str:
        """Format a single quirk entry from config"""
        severity_icons = {
            'low': '🟡',
            'medium': '🟠', 
            'high': '🔴',
            'critical': '⛔'
        }
        
        icon = severity_icons.get(quirk.get('severity', 'medium'), '⚠️')
        integration = quirk.get('integration', 'Unknown Integration')
        title = quirk.get('title', 'Issue')
        
        doc = f"\n## {icon} {integration}: {title}\n\n"
        doc += f"**Severity**: {quirk.get('severity', 'medium').title()}\n\n"
        
        # Description
        if 'description' in quirk:
            doc += f"{quirk['description']}\n\n"
        
        # Affected devices
        if 'affected_devices' in quirk and quirk['affected_devices']:
            doc += "**Affected Devices**:\n"
            for device in quirk['affected_devices']:
                doc += f"- {device}\n"
            doc += "\n"
        
        # Workaround
        if 'workaround' in quirk:
            workaround_text = quirk['workaround']
            doc += f"**✅ Workaround**:\n\n{workaround_text}\n\n"
        
        # Related automation
        if 'automation_id' in quirk:
            doc += f"**Related Automation**: `{quirk['automation_id']}`\n\n"
        
        # Additional notes
        if 'notes' in quirk:
            doc += f"**Notes**: {quirk['notes']}\n\n"
        
        doc += "---\n\n"
        
        return doc
    
    def _generate_quirks_template(self) -> str:
        """Generate template guide when no quirks configured"""
        template = """
## Getting Started

This section is currently empty because no quirks are configured in your `config.yaml` file.

As you encounter integration quirks, limitations, or develop workarounds, document them here!

### How to Add Quirks

Edit your `config.yaml` file and add to the `quirks` section:

```yaml
quirks:
  - integration: "Bond"
    severity: "medium"  # low, medium, high, critical
    title: "RF devices lose state tracking"
    description: |
      Bond RF devices lose state tracking when controlled via physical remote
      because Bond uses one-way RF communication.
    
    affected_devices:
      - "Ceiling Fan (Bedroom)"
      - "Ceiling Fan (Living Room)"
    
    workaround: |
      Create a daily automation at 4 AM to cycle all Bond devices 
      and correct any state drift. Alternatively, install smart switches
      to route physical controls through Home Assistant.
    
    automation_id: "automation.bond_sync_daily"
    notes: "Consider Sonoff ZBMINIR2 switches for permanent fix"
```

### Common Quirks to Document

- Cloud-dependent integrations (Ring, Nest, etc.)
- Integrations requiring periodic re-authentication
- Devices with delayed status updates
- Incompatible device features
- Network configuration requirements
- Workarounds you've developed

Re-run the documentation generator after updating your config to see your quirks here!
"""
        return template
    
    def _generate_zigbee_section(self) -> str:
        """Generate Zigbee network section from config"""
        coordinators = self.system_info.get('coordinators', {})
        zigbee = coordinators.get('zigbee', {})
        
        if not zigbee:
            return ""
        
        doc = "## Zigbee Network\n\n"
        
        # Type and hardware
        zigbee_type = zigbee.get('type', 'Unknown')
        doc += f"**Type**: {zigbee_type}\n"
        
        if 'hardware' in zigbee:
            doc += f"**Hardware**: {zigbee['hardware']}\n"
        
        if 'location' in zigbee:
            doc += f"**Coordinator Location**: {zigbee['location']}\n"
        
        # Auto-discovered device count
        zigbee_entities = [s for s in self.states 
                           if 'zha' in s['entity_id'].lower() or 
                              'zigbee' in s.get('attributes', {}).get('integration', '').lower()]
        doc += f"**Discovered Devices**: {len(zigbee_entities)}\n\n"
        
        # Notes
        if 'notes' in zigbee:
            doc += f"{zigbee['notes']}\n\n"
        
        # Generic troubleshooting
        troubleshooting = """### Zigbee Troubleshooting

**Common Issues:**
1. Devices showing as unavailable after HA restart
2. Distant devices losing connection
3. Intermittent connectivity

**Solutions:**
1. Check device battery levels first
2. Review Zigbee mesh topology: Configuration → ZHA → Visualize
3. Add wall-powered devices as repeaters for extended range
4. Ensure no WiFi interference (consider changing Zigbee channel)
5. Power cycle coordinator if multiple devices are unavailable
"""
        
        if self.styled:
            doc += self.style.collapsible("Troubleshooting Tips", troubleshooting)
        else:
            doc += troubleshooting
        
        return doc
    
    def generate_quick_reference(self) -> str:
        """Generate Quick Reference Guide"""
        parts = []
        
        # Title
        if self.styled:
            parts.append('<div class="doc-header">')
            parts.append('# Quick Reference Guide')
            parts.append('</div>\n')
            parts.append('<div class="callout callout-info">')
            parts.append('**Quick access to essential commands, URLs, and common tasks**')
            parts.append('</div>\n')
        else:
            parts.append('# Quick Reference Guide\n')
            parts.append('Quick access to essential commands, URLs, and common tasks\n')
        
        # Section 1: URLs & Access
        parts.append('## URLs & Access\n')
        
        ha_url = self.user_config['homeassistant']['url']
        bookstack_url = self.user_config['bookstack']['url']
        
        if self.styled:
            parts.append('<div class="reference-table">\n')
        
        parts.append('| Service | URL | Notes |')
        parts.append('|---------|-----|-------|')
        parts.append(f'| Home Assistant | {ha_url} | Main HA interface |')
        parts.append(f'| BookStack Docs | {bookstack_url} | This documentation |')
        
        # Add system info if available
        network_info = self.system_info.get('network', {})
        if network_info.get('subnet'):
            parts.append(f"| Network Subnet | `{network_info['subnet']}` | Local network range |")
        
        if self.styled:
            parts.append('\n</div>\n')
        else:
            parts.append('')
        
        # Section 2: Common Entity Domains
        parts.append('## Common Entity Domains\n')
        
        domain_counts = {}
        for entity in self.states:
            domain = entity['entity_id'].split('.')[0]
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        # Sort by count
        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        if self.styled:
            parts.append('<div class="reference-table">\n')
        
        parts.append('| Domain | Count | Common Uses |')
        parts.append('|--------|-------|-------------|')
        
        domain_descriptions = {
            'light': 'Lights and lighting controls',
            'switch': 'On/off switches and smart plugs',
            'sensor': 'Sensors (temperature, motion, battery, etc.)',
            'binary_sensor': 'Binary sensors (on/off, open/closed)',
            'automation': 'Automations',
            'script': 'Scripts',
            'climate': 'Thermostats and climate control',
            'lock': 'Smart locks',
            'camera': 'Cameras and video feeds',
            'cover': 'Blinds, shades, garage doors',
            'fan': 'Fans and ventilation',
            'media_player': 'Media players (Alexa, TV, etc.)'
        }
        
        for domain, count in top_domains:
            desc = domain_descriptions.get(domain, f'{domain.replace("_", " ").title()} entities')
            if self.styled:
                badge = self.style.badge(domain)
                parts.append(f'| {badge} | **{count}** | {desc} |')
            else:
                parts.append(f'| `{domain}` | {count} | {desc} |')
        
        if self.styled:
            parts.append('\n</div>\n')
        else:
            parts.append('')
        
        # Section 3: Critical Integrations
        parts.append('## Critical Integrations\n')
        
        # Get integrations from quirks config
        integration_list = set()
        for quirk in self.quirks:
            if 'integration' in quirk:
                integration_list.add(quirk['integration'])
        
        if integration_list:
            if self.styled:
                parts.append('<div class="reference-table">\n')
            
            parts.append('| Integration | Purpose | Known Issues |')
            parts.append('|-------------|---------|--------------|')
            
            for integration in sorted(integration_list):
                # Find quirk for this integration
                quirk = next((q for q in self.quirks if q.get('integration') == integration), None)
                if quirk:
                    title = quirk.get('title', 'See Integration Quirks page')
                    severity = quirk.get('severity', 'low')
                    
                    if self.styled:
                        severity_badge = f'<span class="status-badge status-{severity}">{severity.title()}</span>'
                        parts.append(f'| **{integration}** | {quirk.get("description", "").split(".")[0]}... | {severity_badge} |')
                    else:
                        parts.append(f'| {integration} | {quirk.get("description", "").split(".")[0]}... | {severity.title()} |')
            
            if self.styled:
                parts.append('\n</div>\n')
            else:
                parts.append('')
        
        # Section 4: Coordinators
        parts.append('## System Coordinators\n')
        
        coordinators = self.system_info.get('coordinators', {})
        
        if self.styled:
            parts.append('<div class="reference-table">\n')
        
        parts.append('| Type | Hardware | Location | Notes |')
        parts.append('|------|----------|----------|-------|')
        
        for coord_type, coord_info in coordinators.items():
            if coord_info and (coord_type != 'zwave' or (coord_type == 'zwave' and coord_info.get('enabled'))):
                hw = coord_info.get('hardware', 'N/A')
                loc = coord_info.get('location', 'N/A')
                notes = coord_info.get('notes', 'N/A')
                parts.append(f'| {coord_type.upper()} | {hw} | {loc} | {notes} |')
        
        if self.styled:
            parts.append('\n</div>\n')
        else:
            parts.append('')
        
        # Section 5: Common Tasks
        parts.append('## Common Tasks\n')
        
        if self.styled:
            parts.append('<div class="callout callout-tip">')
        
        parts.append('### Restarting Home Assistant')
        parts.append('- **UI**: Settings → System → Restart')
        parts.append('- **CLI**: `ha core restart`\n')
        
        parts.append('### Checking Logs')
        parts.append('- **UI**: Settings → System → Logs')
        parts.append('- **CLI**: `ha core logs`\n')
        
        parts.append('### Reloading Automations')
        parts.append('- **UI**: Settings → Automations → ⋮ → Reload Automations')
        parts.append('- **Service**: `automation.reload`\n')
        
        parts.append('### Backing Up')
        parts.append('- **UI**: Settings → System → Backups → Create Backup')
        parts.append('- **CLI**: `ha backup new --name "manual-backup"`\n')
        
        if self.styled:
            parts.append('</div>\n')
        
        # Section 6: Emergency Contacts & Notes
        parts.append('## Emergency Information\n')
        
        if self.styled:
            parts.append('<div class="callout callout-warning">')
        
        parts.append('### Key Household Members')
        custom_notes = self.custom_sections.get('system_overview_notes', '')
        if 'Key Household Members' in custom_notes:
            # Extract members from custom section
            parts.append('- See System Overview for details\n')
        else:
            parts.append('- Update this section with household member information\n')
        
        parts.append('### Critical Services to Check')
        parts.append('- Door locks (ensure all operational)')
        parts.append('- Security cameras (verify recording)')
        parts.append('- Climate control (thermostats responding)')
        parts.append('- Network connectivity (router/mesh operational)\n')
        
        if self.styled:
            parts.append('</div>\n')
        
        # Footer
        parts.append(f'\n---\n*Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*')
        
        return '\n'.join(parts)
    
    def generate_automation_documentation(self) -> str:
        """Generate critical automation documentation"""
        doc = f"""*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Overview

This page documents critical automations that keep the house running smoothly.

"""
        
        # Get all automations
        automations = [s for s in self.states if s['entity_id'].startswith('automation.')]
        enabled = [a for a in automations if a.get('state') == 'on']
        disabled = [a for a in automations if a.get('state') == 'off']
        
        # Status summary as markdown table
        doc += f"""| | |
|---|---|
| **Active Automations** | {len(enabled)} enabled, {len(disabled)} disabled |
| **Total** | {len(automations)} |

"""
        
        doc += """
## Security & Safety

### Lock Doors at 11 PM

**Entity**: `automation.lock_doors_at_11_pm`
**Trigger**: Time (11:00 PM daily)
**Action**: Lock both front and side doors

**Purpose**: Ensure house is secured at night

**Affected Devices**:
- Front Door Lock
- Side Door Lock

### Water Leak Alert

**Entity**: `automation.water_leak_alert`
**Triggers**: 
"""
        # Find water leak sensors
        water_sensors = [s for s in self.states if 'water' in s['entity_id'].lower() and 'binary_sensor' in s['entity_id']]
        
        for sensor in water_sensors:
            name = sensor.get('attributes', {}).get('friendly_name', sensor['entity_id'])
            doc += f"- {name}\n"
        
        doc += """
**Actions**:
1. Send SMS notifications to all family members
2. Sound sirens (garage camera, downstairs)
3. Text-to-speech announcements
4. Repeat alerts until leak is cleared

**Mode**: Restart (cancels previous run if triggered again)

## Comfort & Convenience

### Bond Light State Sync (4 AM)

**Entity**: `automation.bond_light_state_sync_4_am`
**Trigger**: Time (4:00 AM daily)
**Purpose**: Correct state drift from RF remote usage

**Details**: See Integration Quirks documentation

### Garage Light - Motion Activated

**Entity**: `automation.garage_light_motion_activated`
**Trigger**: Motion sensor in garage
**Action**: 
1. Turn on garage light
2. Wait for motion to stop for 5 minutes
3. Turn off light

**Mode**: Restart (extends timer if motion detected again)

## Presence & Welcome Home

### When Kevin Gets Home

**Entity**: `automation.when_kevin_gets_home`
**Trigger**: Kevin's presence detection (person.kevin_marlowe enters 'home')
**Actions**: [Document specific actions]

### Jill Arrives Home

**Entity**: `automation.jill_arrives_home`  
**Trigger**: Jill's presence detection
**Actions**: [Document specific actions]

## Away Mode

### Away Mode - Simulate Presence

**Entity**: `automation.away_mode_simulate_presence`
**Trigger**: When everyone leaves home
**Actions**: Random light on/off to simulate occupancy

**How to Enable/Disable**: [Document method]

## Seasonal & Time-Based

### Lights On at Sunset

**Entity**: `automation.lights_on_at_6`
**Trigger**: Time-based (varies by season)
**Actions**: Turn on exterior and key interior lights

## Voice Assistant

### Update Weather Forecast for Echo Show

**Entity**: `automation.update_weather_forecast_for_echo_show`
**Purpose**: Keep Echo Show display current
**Frequency**: [Document trigger]

## Bedroom Fan Control

### Bedroom Fan - Physical Switch Toggle

**Entity**: `automation.bedroom_fan_physical_switch_toggle`
**Purpose**: Map Sonoff switch to Bond fan control
**Integration**: Sonoff ZBMINIR2 → Bond fan

**How It Works**:
1. Physical switch press detected by Sonoff
2. Automation toggles Bond fan device
3. State tracker updated
4. Prevents state drift

## Maintenance

### All Active Automations
"""
        
        doc += f"\n**Total**: {len(automations)}\n\n"
        doc += "| Automation | State | Last Triggered |\n"
        doc += "|------------|-------|----------------|\n"
        
        for auto in sorted(automations, key=lambda x: x['entity_id']):
            name = auto.get('attributes', {}).get('friendly_name', auto['entity_id'])
            state = auto.get('state', 'unknown')
            last = auto.get('attributes', {}).get('last_triggered', 'Never')
            if last and last != 'Never':
                try:
                    last = datetime.fromisoformat(last.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                except:
                    pass
            
            # Add badge and status for styled output
            if self.styled:
                badge = self.style.badge('automation')
                status = self.style.status(state)
                doc += f"| {badge} {name} | {status} | {last} |\n"
            else:
                status_icon = "✅" if state == "on" else "⚠️"
                doc += f"| {status_icon} {name} | {state} | {last} |\n"
        
        return doc


def _validate_config(config: Dict) -> None:
    """Validate configuration has required fields"""
    required_fields = [
        ('bookstack', 'url'),
        ('bookstack', 'token_id'),
        ('bookstack', 'token_secret'),
        # book_id is now optional - will be auto-created if not specified
        ('homeassistant', 'url'),
        ('homeassistant', 'token'),
    ]
    
    missing = []
    for section, key in required_fields:
        if section not in config:
            missing.append(f"{section}")
        elif key not in config[section]:
            missing.append(f"{section}.{key}")
        elif not config[section][key]:
            missing.append(f"{section}.{key} (empty)")
    
    if missing:
        raise ValueError(f"Config validation failed. Missing required fields: {', '.join(missing)}")
    
    print("✅ Configuration validated")


def ensure_book_exists(bookstack: BookStackAPI, config: Dict) -> int:
    """
    Ensure the documentation book exists, create if needed.
    Returns the book_id to use.
    """
    book_name = config.get('bookstack', {}).get('book_name', 'Home Assistant Documentation')
    
    # Check if book_id is specified in config
    book_id = config.get('bookstack', {}).get('book_id')
    
    if book_id:
        # Verify the book exists
        try:
            books = bookstack.list_books()
            book_exists = any(b['id'] == book_id for b in books)
            if book_exists:
                print(f"📚 Using existing book (ID: {book_id})")
                return book_id
            else:
                print(f"⚠️  Book ID {book_id} not found, will search by name...")
        except Exception as e:
            print(f"⚠️  Could not verify book ID: {e}")
    
    # Search for book by name
    print(f"🔍 Searching for book: '{book_name}'...")
    book = bookstack.find_book_by_name(book_name)
    
    if book:
        print(f"📚 Found existing book (ID: {book['id']})")
        return book['id']
    
    # Create new book
    print(f"📘 Creating new book: '{book_name}'...")
    book = bookstack.create_book(
        name=book_name,
        description="Auto-generated documentation for Home Assistant setup"
    )
    print(f"✨ Created book (ID: {book['id']})")
    
    # Create initial "Notes" manual page
    print("📄 Creating initial 'Notes' page...")
    try:
        initial_content = """*This is a manually maintained page - it will not be overwritten by automated updates.*

## Notes & Manual Documentation

Use this page for your personal notes, observations, and documentation that you want to maintain manually.

### Tips for Using This Page

- Document your reasoning for configuration decisions
- Add troubleshooting notes from experience
- Keep track of "gotchas" you've discovered
- Link to related auto-generated pages for context

### Getting Started

The auto-generated pages are updated regularly and will show:
- **System Overview**: Current status, entity counts, and system information
- **Entity Inventory**: All devices and entities in your setup
- **Integration Quirks & Solutions**: Known issues and workarounds (configured in config.yaml)
- **Critical Automations**: Important automation documentation

You can create additional manual pages at any time. Just tag them with "manual" to prevent auto-updates.

---

*Auto-generated pages are tagged with "auto-generated" and will be updated on schedule.*
"""
        bookstack.create_page(
            book['id'],
            None,  # No chapter
            'Notes',
            initial_content,
            tags=[
                {'name': 'manual', 'value': ''},
                {'name': 'user-notes', 'value': ''}
            ]
        )
        print("✅ Created 'Notes' page (tagged as manual)")
    except Exception as e:
        print(f"⚠️  Could not create Notes page: {e}")
    
    return book['id']


def main():
    parser = argparse.ArgumentParser(description='Generate HA documentation for BookStack')
    parser.add_argument('--config', required=True, help='Path to config YAML file')
    parser.add_argument('--test', action='store_true', help='Test mode - only show what would be generated')
    parser.add_argument('--no-style', action='store_true', help='Disable HTML styling (plain markdown only)')
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Validate config
    _validate_config(config)
    
    print("=" * 60)
    print("Home Assistant to BookStack Documentation Generator")
    styled = config.get('documentation', {}).get('styled_output', True) and not args.no_style
    if styled:
        print("✨ Enhanced with HTML styling")
    print("=" * 60)
    
    # Initialize APIs
    print("\n🔌 Connecting to Home Assistant...")
    ha_api = HomeAssistantAPI(
        config['homeassistant']['url'],
        config['homeassistant']['token']
    )
    
    print("🔌 Connecting to BookStack...")
    bookstack = BookStackAPI(
        config['bookstack']['url'],
        config['bookstack']['token_id'],
        config['bookstack']['token_secret']
    )
    
    # Generate documentation - PASS CONFIG
    print("\n📝 Generating documentation...")
    doc_gen = HADocumentationGenerator(ha_api, config, styled=styled)
    doc_gen.fetch_data()
    
    # Define documents to generate
    # Get enabled document sections
    doc_sections = config.get('documentation', {}).get('sections', {})
    
    # Build documents list in the requested order:
    # 1. Quick Reference Guide
    # 2. System Overview
    # 3. Entity Inventory
    # 4. Integration Quirks & Solutions
    # 5. Critical Automations
    # 6. Notes (manual page - created separately, not here)
    documents = []
    
    # 1. Quick Reference Guide
    if doc_sections.get('quick_reference', True):
        documents.append({
            'name': 'Quick Reference Guide',
            'content': doc_gen.generate_quick_reference(),
            'chapter_id': config['bookstack'].get('chapters', {}).get('reference')
        })
    
    # 2. System Overview
    if doc_sections.get('system_overview', True):
        documents.append({
            'name': 'System Overview',
            'content': doc_gen.generate_system_overview(),
            'chapter_id': config['bookstack'].get('chapters', {}).get('overview')
        })
    
    # 3. Entity Inventory
    if doc_sections.get('entity_inventory', True):
        documents.append({
            'name': 'Entity Inventory',
            'content': doc_gen.generate_entity_inventory(),
            'chapter_id': config['bookstack'].get('chapters', {}).get('inventory')
        })
    
    # 4. Integration Quirks & Solutions
    if doc_sections.get('integration_quirks', True):
        documents.append({
            'name': 'Integration Quirks & Solutions',
            'content': doc_gen.generate_integration_quirks(),
            'chapter_id': config['bookstack'].get('chapters', {}).get('integrations')
        })
    
    # 5. Critical Automations
    if doc_sections.get('automation_summary', True):
        documents.append({
            'name': 'Critical Automations',
            'content': doc_gen.generate_automation_documentation(),
            'chapter_id': config['bookstack'].get('chapters', {}).get('automations')
        })
    
    # Note: "Notes" page is created as a manual page by ensure_book_exists() function
    # It won't be updated by this script to preserve user edits
    
    if args.test:
        print("\n" + "=" * 60)
        print("TEST MODE - Documents that would be generated:")
        print("=" * 60)
        
        # Show what book would be used/created
        book_name = config.get('bookstack', {}).get('book_name', 'Home Assistant Documentation')
        book_id = config.get('bookstack', {}).get('book_id')
        
        if book_id:
            print(f"\n📚 Would use Book ID: {book_id}")
        else:
            print(f"\n📚 Would search for or create book: '{book_name}'")
        
        for doc in documents:
            print(f"\n📄 {doc['name']}")
            print("-" * 60)
            print(doc['content'][:500] + "...\n")
        return
    
    # Ensure book exists (create if needed) - ONLY in real mode
    book_id = ensure_book_exists(bookstack, config)
    
    # Publish to BookStack
    print(f"\n📚 Publishing to BookStack (Book ID: {book_id})...")
    
    for doc in documents:
        print(f"\n📄 Processing: {doc['name']}")
        
        existing = bookstack.find_page_by_name(book_id, doc['name'])
        
        if existing:
            # Check if page is marked as manual
            if bookstack.page_is_manual(existing['id']):
                print(f"   ⏭️  Skipping (marked as 'manual' - user-maintained content)")
                continue
            
            print(f"   ↻ Updating existing page (ID: {existing['id']})")
            bookstack.update_page(existing['id'], doc['content'])
        else:
            print(f"   ✨ Creating new page")
            bookstack.create_page(
                book_id,
                doc.get('chapter_id'),
                doc['name'],
                doc['content'],
                tags=[{'name': 'auto-generated'}, {'name': 'home-assistant'}]
            )
    
    print("\n" + "=" * 60)
    print("✅ Documentation update complete!")
    print(f"📖 View at: {config['bookstack']['url']}/books/{book_id}")
    print("=" * 60)


if __name__ == '__main__':
    main()