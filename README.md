# Blocky for Home Assistant

A custom Home Assistant integration for [Blocky](https://github.com/0xERR0R/blocky), the DNS proxy and ad blocker.

## Installation with HACS

This integration is distributed as a HACS custom repository.

1. Open HACS and choose **Custom repositories** from the menu.
2. Add this repository URL and select **Integration**.
3. Download **Blocky**.
4. Restart Home Assistant.
5. Add **Blocky** from **Settings > Devices & services**.

## Requirements

- Blocky 0.34 or newer.
- Blocky's HTTP API must be reachable from Home Assistant.
- Blocky statistics should be enabled with `statistics.enable: true` for the statistics sensors. Blocking controls remain available when statistics are disabled.

The integration uses the following Blocky API endpoints by default:

| Purpose | Method | Path |
| --- | --- | --- |
| Blocking status | GET | `/api/blocking/status` |
| Enable blocking | GET | `/api/blocking/enable` |
| Disable blocking | GET | `/api/blocking/disable` |
| Refresh lists | POST | `/api/lists/refresh` |
| Statistics | GET | `/api/stats` |

All paths can be changed during setup or reconfiguration. This supports reverse proxies and path rewrites. Optional HTTP Basic Auth credentials are sent to every request for nginx or another proxy in front of Blocky.

## Entities and actions

The integration creates one Blocky device with:

- Sensors for the 24-hour query summary and current cache entries.
- A switch for enabling and disabling blocking.
- A button for refreshing lists.

The `blocky.disable_for_duration` action accepts:

```yaml
action: blocky.disable_for_duration
target:
  config_entry_id: YOUR_BLOCKY_CONFIG_ENTRY_ID
  duration: 30m
  groups: ads,tracker
```

`groups` is optional. The duration uses Blocky's Go duration syntax, such as `5m`, `1h`, or `5m30s`.

## Troubleshooting

If the sensors are unavailable while the switch still works, enable statistics in Blocky and restart or reload the integration. A `401` or `403` response means the configured proxy credentials need to be corrected.

## Development

Run the test suite with:

```bash
pytest
```

The repository also includes HACS validation and Home Assistant Hassfest workflows.
