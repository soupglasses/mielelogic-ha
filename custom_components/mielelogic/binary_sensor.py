"""Binary sensor platform for MieleLogic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, MACHINE_KIND_ICON
from .coordinator import MieleLogicCoordinator
from .entity import MieleLogicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MieleLogicConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MieleLogicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MieleLogic binary sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []

    for (laundry_num, machine_num), machine in coordinator.data.machine_states.items():
        laundry = coordinator.data.laundries.get(laundry_num)
        laundry_name = laundry.name if laundry else f"Laundry {laundry_num}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{laundry_num}_{machine_num}")},
            name=machine.unit_name,
            manufacturer="Miele",
            model=machine.machine_kind.name,
            suggested_area=laundry_name,
        )

        entities.append(
            MachineMineBinary(
                coordinator=coordinator,
                device_info=device_info,
                laundry_number=laundry_num,
                machine_number=machine_num,
                entry_id=entry.entry_id,
            )
        )

    async_add_entities(entities)


class MachineMineBinary(MieleLogicEntity, BinarySensorEntity):
    """Binary sensor that is ON when this machine was started or reserved by us.

    Pairs naturally with the machine_status enum sensor:
    - is_on=True + status="running"        → we are running a cycle
    - is_on=True + status="reserved"       → the machine is currently reserved by us
    - is_on=False                          → machine belongs to someone else (or is idle)

    This sensor has no device_class so Home Assistant displays it as "On" / "Off"
    rather than the misleading "Running" / "Not running" labels of the RUNNING class.
    """

    _attr_translation_key = "machine_mine"

    def __init__(
        self,
        coordinator: MieleLogicCoordinator,
        device_info: DeviceInfo,
        laundry_number: int,
        machine_number: int,
        entry_id: str,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            device_info=device_info,
            unique_id=f"{entry_id}_{laundry_number}_{machine_number}_mine",
        )
        self._laundry_number = laundry_number
        self._machine_number = machine_number

    @property
    def icon(self) -> str | None:
        key = (self._laundry_number, self._machine_number)
        machine = self.coordinator.data.machine_states.get(key)
        if machine is None:
            return None
        return MACHINE_KIND_ICON.get(machine.machine_kind)

    @property
    def is_on(self) -> bool | None:
        key = (self._laundry_number, self._machine_number)
        machine = self.coordinator.data.machine_states.get(key)
        if machine is None:
            return None
        return key in self.coordinator.data.our_machines
