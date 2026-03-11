"""Sensor platform for MieleLogic."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo

from mielelogic_api.dto import MachineStatus, MachineTextStatus

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
    """Set up MieleLogic sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

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
            MachineStatusSensor(
                coordinator=coordinator,
                device_info=device_info,
                laundry_number=laundry_num,
                machine_number=machine_num,
                entry_id=entry.entry_id,
            )
        )
        entities.append(
            MachineMinutesRemainingSensor(
                coordinator=coordinator,
                device_info=device_info,
                laundry_number=laundry_num,
                machine_number=machine_num,
                entry_id=entry.entry_id,
            )
        )

    if coordinator.data.currency:
        entities.append(
            AccountBalanceSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
            )
        )

    async_add_entities(entities)


class MachineStatusSensor(MieleLogicEntity, SensorEntity):
    """Enum sensor showing the current machine status.

    States
    ------
    idle           Machine is free.
    busy           Machine is running — started by someone else.
    running        Machine is running — started by us (transaction detected).
    reserved Machine is reserved — reserved by us.
    booked   Machine is reserved — reserved by someone else.
    closed   Machine is closed / out of service.
    disabled Machine is administratively disabled.
    """

    _attr_translation_key = "machine_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "idle",
        "busy",
        "running",
        "reserved",
        "booked",
        "closed",
        "disabled",
    ]

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
            unique_id=f"{entry_id}_{laundry_number}_{machine_number}_status",
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
    def native_value(self) -> str | None:
        key = (self._laundry_number, self._machine_number)
        machine = self.coordinator.data.machine_states.get(key)
        if machine is None:
            return None

        # Color-based states are unambiguous — check these first
        if machine.machine_status == MachineStatus.Closed:
            return "closed"
        if machine.machine_status == MachineStatus.Disabled:
            return "disabled"

        ours = key in self.coordinator.data.our_machines
        match machine.machine_text_status:
            case MachineTextStatus.Idle:
                return "idle"
            case MachineTextStatus.Running:
                return "running" if ours else "busy"
            case MachineTextStatus.Reserved:
                return "reserved" if ours else "booked"
            case _:
                # Unknown text1 on a non-idle machine, treat as busy
                return "running" if ours else "busy"

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None]:
        key = (self._laundry_number, self._machine_number)
        machine = self.coordinator.data.machine_states.get(key)
        if machine is None:
            return {}
        reserved_until = machine.reserved_until
        return {
            "minutes_remaining": machine.minutes_remaining,
            "reserved_until": reserved_until.strftime("%H:%M")
            if reserved_until
            else None,
            "machine_kind": machine.machine_kind.name,
            "machine_type": machine.machine_type,
            "group_number": machine.group_number,
        }


def _minutes_until(target: dt.time) -> int:
    """Minutes from now until a wall-clock time, wrapping past midnight."""
    now = dt.datetime.now()
    target_dt = now.replace(
        hour=target.hour, minute=target.minute, second=0, microsecond=0
    )
    if target_dt <= now:
        target_dt += dt.timedelta(days=1)
    return max(0, int((target_dt - now).total_seconds() / 60))


class MachineMinutesRemainingSensor(MieleLogicEntity, SensorEntity):
    """Numeric sensor showing minutes remaining on a running or booked machine.

    - Running (running / busy): value comes directly from text2 ("28 mins" → 28).
    - Reserved / booked: value is computed as minutes until the reserved_until clock
      time, wrapping past midnight if needed.
    - Idle / closed / disabled: unavailable (None).

    Use this sensor to trigger automations shortly before a cycle or booking ends.
    """

    _attr_translation_key = "minutes_remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

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
            unique_id=f"{entry_id}_{laundry_number}_{machine_number}_minutes_remaining",
        )
        self._laundry_number = laundry_number
        self._machine_number = machine_number

    @property
    def native_value(self) -> int | None:
        key = (self._laundry_number, self._machine_number)
        machine = self.coordinator.data.machine_states.get(key)
        if machine is None:
            return None
        if machine.minutes_remaining is not None:
            return machine.minutes_remaining
        if machine.reserved_until is not None:
            return _minutes_until(machine.reserved_until)
        return None


class AccountBalanceSensor(MieleLogicEntity, SensorEntity):
    """Sensor showing the account balance."""

    _attr_translation_key = "account_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: MieleLogicCoordinator,
        entry_id: str,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            device_info=DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_account")},
                name="MieleLogic Account",
                manufacturer="Miele",
            ),
            unique_id=f"{entry_id}_account_balance",
        )

    @property
    def native_value(self) -> float:
        return self.coordinator.data.balance

    @property
    def native_unit_of_measurement(self) -> str:
        return self.coordinator.data.currency
