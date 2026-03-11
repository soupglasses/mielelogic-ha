"""Constants for the MieleLogic integration."""

from logging import Logger, getLogger

from mielelogic_api.dto import MachineKind

LOGGER: Logger = getLogger(__package__)

DOMAIN = "mielelogic"

CONF_SCOPE = "scope"

MACHINE_KIND_ICON: dict[MachineKind, str] = {
    MachineKind.Washer: "mdi:washing-machine",
    MachineKind.Dryer: "mdi:tumble-dryer",
    MachineKind.Mangler: "mdi:iron",
    MachineKind.Coffee: "mdi:coffee-maker",
    MachineKind.Shower: "mdi:shower",
    MachineKind.Spa: "mdi:hot-tub",
    MachineKind.Sauna: "mdi:sauna",
    MachineKind.Solarium: "mdi:weather-sunny",
}
