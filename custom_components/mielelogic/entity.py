"""Base entity for the MieleLogic integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MieleLogicCoordinator


class MieleLogicEntity(CoordinatorEntity[MieleLogicCoordinator]):
    """Base class for MieleLogic entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MieleLogicCoordinator,
        device_info: DeviceInfo,
        unique_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
