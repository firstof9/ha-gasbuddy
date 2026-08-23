---
name: virtual_hub
description: Overview of the Virtual Hub design pattern used to manage shared settings centrally across multiple GasBuddy station configurations.
---

# Virtual Hub Architecture

The custom component implements a Virtual Hub config entry (`unique_id = "hub"`) to hold global settings shared across individual station entries.

## Keys Shared Centrally

- `solver`: The FlareSolverr URL used to bypass Cloudflare.
- `timeout`: Request timeout in milliseconds.
- `brand_adjustments`: Price adjustments per brand configured as a YAML block.

## How it works in code

### 1. Dynamic Settings Resolution
The update coordinator resolves settings using `self._get_hub_setting(key, default)`. This helper automatically checks for an active `"hub"` config entry first and returns its options. If not found, it falls back to the individual station's config:

```python
def _get_hub_setting(self, key: str, default: Any = None) -> Any:
    for entry in self.hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == "hub":
            val = entry.options.get(key) or entry.data.get(key)
            if val is not None:
                return val
    return self._config.options.get(key) or self._config.data.get(key, default)
```

### 2. Device Registry Nesting
The Hub config entry registers a central device in the Home Assistant device registry. Station sensors specify `via_device=(DOMAIN, "hub")` in their `device_info` to visually group the stations under the main Hub card in the UI.

### 3. Automatic Settings Migration
When the Hub entry is set up, a routine automatically imports and merges the solver, timeout, and brand adjustments from any existing station entries into the Hub, and removes those options from the stations to prevent stale duplicates.
