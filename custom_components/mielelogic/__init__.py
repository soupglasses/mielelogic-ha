"""MieleLogic integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.util.ssl import get_default_context

from mielelogic_api import MieleLogicClient

from .const import CONF_SCOPE
from .coordinator import MieleLogicCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import MieleLogicConfigEntry

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

POLL_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MieleLogicConfigEntry,
) -> bool:
    """Set up MieleLogic from a config entry."""
    ssl_context = await hass.async_add_executor_job(get_default_context)
    client = MieleLogicClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        scope=entry.data[CONF_SCOPE],
        ssl_context=ssl_context,
    )
    await client.connect()

    coordinator = MieleLogicCoordinator(
        hass=hass,
        client=client,
        update_interval=POLL_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MieleLogicConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok
