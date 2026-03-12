"""Tests for MieleLogic sensor state logic.

The sensor's native_value is derived from MachineStateDTO.machine_text_status plus
the coordinator's our_machines set. These tests cover the DTO-level parsing that
drives sensor output.
"""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorStateClass

from custom_components.mielelogic.sensor import AccountBalanceSensor
from mielelogic_api.dto import MachineTextStatus

from tests.support.factories import MachineStateDTOFactory


def _machine(machine_color: int, text1: str, text2: str = ""):
    return MachineStateDTOFactory.build(
        machine_color=machine_color,
        text1=text1,
        text2=text2,
    )


class TestMachineTextStatus:
    """Test the text_status computed field on MachineStateDTO."""

    def test_idle_by_color(self):
        machine = _machine(machine_color=1, text1="Idle")
        assert machine.machine_text_status == MachineTextStatus.Idle

    def test_idle_overrides_text1(self):
        """Idle color always wins, even if text1 contains unexpected content."""
        machine = _machine(machine_color=1, text1="Time left")
        assert machine.machine_text_status == MachineTextStatus.Idle

    def test_timed_run(self):
        machine = _machine(machine_color=2, text1="Time left", text2="28 min")
        assert machine.machine_text_status == MachineTextStatus.Running

    def test_timed_run_with_live_snapshot_casing(self):
        machine = _machine(machine_color=2, text1="Time left", text2="48 min")
        assert machine.machine_text_status == MachineTextStatus.Running

    def test_reserved(self):
        machine = _machine(machine_color=2, text1="Reserved until", text2="20:08")
        assert machine.machine_text_status == MachineTextStatus.Reserved

    def test_unknown_busy(self):
        machine = _machine(machine_color=2, text1="Something unexpected")
        assert machine.machine_text_status == MachineTextStatus.Unknown


class TestMinutesRemaining:
    """Test minutes_remaining parsing from text2."""

    def test_parses_minutes(self):
        machine = _machine(machine_color=2, text1="Time left", text2="28 min")
        assert machine.minutes_remaining == 28

    def test_parses_large_minutes(self):
        machine = _machine(machine_color=2, text1="Time left", text2="70 min")
        assert machine.minutes_remaining == 70

    def test_parses_minutes_with_live_snapshot_format(self):
        machine = _machine(machine_color=2, text1="Time left", text2="48 min")
        assert machine.minutes_remaining == 48

    def test_parses_first_number_only(self):
        machine = _machine(machine_color=2, text1="Time left", text2="5 min")
        assert machine.minutes_remaining == 5

    def test_none_when_idle(self):
        machine = _machine(machine_color=1, text1="Idle", text2=" ")
        assert machine.minutes_remaining is None

    def test_none_when_reserved(self):
        machine = _machine(machine_color=2, text1="Reserved until", text2="20:08")
        assert machine.minutes_remaining is None

    def test_none_when_text2_empty(self, caplog):
        """Missing number in text2 should warn and return None."""
        machine = _machine(machine_color=2, text1="Time left", text2="")
        with caplog.at_level("WARNING"):
            result = machine.minutes_remaining
        assert result is None
        assert "could not parse minutes" in caplog.text


class TestReservedUntil:
    """Test reserved_until parsing from text2."""

    def test_parses_time(self):
        machine = _machine(machine_color=2, text1="Reserved until", text2="20:08")
        assert machine.reserved_until == dt.time(20, 8)

    def test_parses_time_embedded_in_text(self):
        machine = _machine(machine_color=2, text1="Reserved until", text2="Until 9:30")
        assert machine.reserved_until == dt.time(9, 30)

    def test_none_when_not_reserved(self):
        machine = _machine(machine_color=2, text1="Time left", text2="28 min")
        assert machine.reserved_until is None

    def test_none_when_idle(self):
        machine = _machine(machine_color=1, text1="Idle", text2=" ")
        assert machine.reserved_until is None

    def test_none_when_text2_missing(self, caplog):
        """Missing HH:MM in text2 should warn and return None."""
        machine = _machine(
            machine_color=2, text1="Reserved until", text2="no time here"
        )
        with caplog.at_level("WARNING"):
            result = machine.reserved_until
        assert result is None
        assert "could not parse HH:MM" in caplog.text


def test_account_balance_sensor_uses_total_state_class():
    """Monetary account balances must report as totals in Home Assistant."""
    coordinator = MagicMock()
    coordinator.data = SimpleNamespace(balance=12.5, currency="DKK")

    sensor = AccountBalanceSensor(coordinator=coordinator, entry_id="test-entry")

    assert sensor.state_class is SensorStateClass.TOTAL
