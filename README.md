# MieleLogic Home Assistant Integration

MieleLogic is a Home Assistant custom integration for MieleLogic laundry rooms.
It makes it easier to bring your shared laundry machines into Home Assistant if
your building already uses MieleLogic.

## Usage

To start, add this repository to HACS:

[![Open HACS in My Home Assistant][repository-badge]][repository-url]

Add this repository manually in HACS:

1. Navigate to "HACS" in your Home Assistant web interface.
2. Under the "⋮" actions menu in the top corner, choose "Custom repositories".
3. Add `https://github.com/soupglasses/mielelogic-ha` as a repository in the "Integration" category.
4. After a short bit, searching for "MieleLogic" should show the integration from this repository.
5. Press "MieleLogic" and choose "Download".
6. Restart Home Assistant.
7. Navigate to "Settings" -> "Devices & services" -> "Add integration".
8. Search for "MieleLogic".
9. Enter your MieleLogic username, password, and country (`Denmark` or `Norway`).

Home Assistant should now create entities for your machines. Further information
is available below, including example automations.

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [poe](https://poethepoet.natn.io/) for task running.

### Quick Start

```bash
# Activate the project environment
source .venv/bin/activate
# or
source .envrc

# Install dependencies and set up pre-commit hooks
poe setup

# Run tests
poe test
poe test-ha

# Other useful commands
poe console   # Interactive Python shell with project loaded
poe lint      # Check code style
poe format    # Auto-format code
poe build     # Build distribution packages
```

`poe test` runs the library test suite from the shared development environment. Tests marked with
`@pytest.mark.network` opt back in to real network access for that test only.

`poe test-ha` runs the Home Assistant integration tests from
`tests/custom_components/mielelogic` in the same
shared development environment.

## Working On HA

The Home Assistant integration code lives in `custom_components/mielelogic/`.
Its tests live in `tests/custom_components/mielelogic/`.

The rest of the test suite is split by package:

- `tests/mielelogic_cli/` for CLI coverage
- `tests/mielelogic_api/` for the API client library
- `tests/custom_components/mielelogic/` for the Home Assistant integration

For one-off HA commands, run them from the shared environment:

```bash
pytest tests/custom_components/mielelogic
poe develop
```

`poe develop` runs Home Assistant against `.ha-dev-config` and restarts it when
files change under `custom_components/mielelogic/` or `mielelogic_api/`. For
local development it copies the integration into `.ha-dev-config` and removes
the production PyPI requirement from that copied manifest, because the dev venv
already installs the repo editable. Use `scripts/develop --once` when you want
a single foreground HA run without the watcher.

Normal setup installs both the library and HA tooling into the same `.venv`:

```bash
uv sync
```

Then use the usual task wrappers:

```bash
poe test
poe test-ha
poe develop
```

## Packaging and Releases

The Python client library is published to PyPI as `mielelogic-api` while keeping the
import path `mielelogic_api`.

The Home Assistant integration depends on that published package through
`custom_components/mielelogic/manifest.json`, so Home Assistant OS must be able to
install the exact released version from PyPI.

Maintainer release flow:

1. Ensure `custom_components/mielelogic/manifest.json` pins the intended
   `mielelogic-api==X.Y.Z` release.
2. Create and push the matching git tag `vX.Y.Z`.
3. GitHub Actions builds and publishes the package to PyPI using trusted publishing.

## Authentication Note

MieleLogic's internal OAuth2 lifecycle is seemingly not long-lived: tokens are
invalidated aggressively, so sessions do not remain valid indefinitely.
Meaning that this project cannot use the Home Assistant's native OAuth2
flow by default, since it expects long-lived stable tokens.

### Requirements

- uv (install via `pip install uv` or see [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/))

## Automations

The integration exposes three entities per machine — a status sensor, a time-remaining
sensor, and a "mine" binary sensor — designed to work together cleanly in automations.

### Entity overview

| Entity | Type | Example states / value |
|---|---|---|
| `sensor.<machine>_status` | Enum | `idle`, `busy`, `running`, `reserved`, `booked`, `closed`, `disabled` |
| `sensor.<machine>_time_remaining` | Duration (min) | `28`, `5`, `null` (unavailable when idle/closed/disabled) |
| `binary_sensor.<machine>_mine` | Boolean | `on` (started/reserved by me), `off` |

**Status state meanings:**

- `idle` — machine is free
- `busy` — running, started by someone else
- `running` — running, started by you (transaction detected within 10 min window)
- `reserved` — currently reserved by you
- `booked` — currently reserved by someone else
- `closed` / `disabled` — out of service

The integration detects ownership by correlating your recent transactions (fetched from
the API within a 10-minute rolling window) with idle→active state transitions.  No
transaction check is needed when a machine goes back to idle — that transition always
clears the "mine" flag.

### Notify when your laundry is done

Trigger on `running` → `idle` for any machine you started.

```yaml
automation:
  - alias: "Laundry done"
    trigger:
      - platform: state
        entity_id:
          - sensor.vask_1_status
          - sensor.tumbler_1_status
        from: "running"
        to: "idle"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Laundry done"
          message: "{{ trigger.to_state.attributes.friendly_name }} has finished."
```

### Notify ~1 minute before a cycle ends

The `time_remaining` sensor counts down while the machine is running. Trigger when it
drops below 2 minutes (API polling resolution means you may not catch exactly 1).

```yaml
automation:
  - alias: "Laundry almost done"
    trigger:
      - platform: numeric_state
        entity_id:
          - sensor.vask_1_time_remaining
          - sensor.tumbler_1_time_remaining
        below: 2
    condition:
      # Only fire when it is our machine, not someone else's
      - condition: template
        value_template: >
          {{ states('sensor.' ~ trigger.entity_id.split('.')[1].replace('_time_remaining', '_status')) == 'running' }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Almost done"
          message: >
            {{ trigger.to_state.attributes.friendly_name | replace(' time remaining', '') }}
            finishes in about 1 minute.
```

### Notify when all your machines finish (group trigger)

If you often run washer + dryer simultaneously, wait until both are done before notifying.

```yaml
automation:
  - alias: "All laundry done"
    mode: single
    trigger:
      - platform: state
        entity_id:
          - sensor.vask_1_status
          - sensor.tumbler_1_status
        from: "running"
        to: "idle"
    condition:
      # Fire only when none of your machines are still running
      - condition: template
        value_template: >
          {% set mine = ['sensor.vask_1_status', 'sensor.tumbler_1_status'] %}
          {{ mine | map('states') | select('eq', 'running') | list | count == 0 }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "All laundry done"
          message: "All your machines have finished."
```

### Check if a machine is booked by someone else before going down

```yaml
condition:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.vask_1_status
        state: "booked"
```

## Legal Disclaimer

*This project is an independent, unofficial integration and is not endorsed by, affiliated with, or sponsored by Miele & Cie. KG, its subsidiaries, or MieleLogic. All product names, logos, brands, trademarks, and registered trademarks are property of their respective owners.*

**Usage is at your own risk!**

### Trademark Notice

*Miele® and MieleLogic® are registered trademarks of their respective owners. This project's use of these names is for identification and reference purposes only and does not imply any endorsement or affiliation.*

[repository-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[repository-url]: https://my.home-assistant.io/redirect/hacs_repository/?owner=soupglasses&repository=mielelogic-ha&category=integration
