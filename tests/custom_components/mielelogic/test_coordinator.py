"""Tests for the MieleLogic coordinator's 'ours' detection logic."""

import datetime as dt
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mielelogic.coordinator import (
    MieleLogicData,
    MieleLogicCoordinator,
)
from mielelogic_api.dto import MachineTextStatus

from tests.support.factories import (
    DetailsResponseDTOFactory,
    MachineStateDTOFactory,
    LaundryStatesResponseDTOFactory,
    TransactionDTOFactory,
    TransactionResponseDTOFactory,
)


def _idle(laundry_number: int, machine_number: int):
    return MachineStateDTOFactory.build(
        laundry_number=laundry_number,
        machine_number=machine_number,
        machine_color=1,  # MachineStatus.Idle
        text1="Idle",
        text2=" ",
    )


def _busy(laundry_number: int, machine_number: int):
    return MachineStateDTOFactory.build(
        laundry_number=laundry_number,
        machine_number=machine_number,
        machine_color=2,  # MachineStatus.Busy
        text1="Time left",
        text2="28 min",
    )


def _reserved(laundry_number: int, machine_number: int):
    # Reservation payload shape is not yet backed by live snapshots.
    return MachineStateDTOFactory.build(
        laundry_number=laundry_number,
        machine_number=machine_number,
        machine_color=2,  # MachineStatus.Busy
        text1="Reserved",
        text2="20:08",
    )


@pytest.fixture
def coordinator(hass):
    return MieleLogicCoordinator(
        hass=hass,
        client=MagicMock(),
        update_interval=timedelta(minutes=1),
    )


class TestOurMachineDetection:
    """Test the _detect_our_machines logic in isolation."""

    def test_transaction_then_busy_marks_ours(self, coordinator):
        """Machine should be 'ours' when: transaction appears, then machine goes busy."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        tx = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        result = coordinator._detect_our_machines({key: _idle(1000, 1)}, [tx], now)
        assert key not in result

        result = coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [], now + dt.timedelta(minutes=2)
        )
        assert key in result

    def test_busy_then_transaction_marks_ours(self, coordinator):
        """Machine should be 'ours' when: machine goes busy, then transaction appears."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        result = coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [], now + dt.timedelta(minutes=1)
        )
        assert key not in result

        tx = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        result = coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [tx], now + dt.timedelta(minutes=3)
        )
        assert key in result

    def test_transaction_too_late_not_ours(self, coordinator):
        """Machine should NOT be 'ours' when transaction is >5min after busy."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [], now + dt.timedelta(minutes=1)
        )

        tx = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        result = coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [tx], now + dt.timedelta(minutes=7)
        )
        assert key not in result

    def test_machine_returns_to_idle_clears_ours(self, coordinator):
        """Machine should be cleared from 'ours' when it returns to idle."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        tx = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [tx], now + dt.timedelta(minutes=1)
        )
        assert key in coordinator._our_machines

        result = coordinator._detect_our_machines(
            {key: _idle(1000, 1)}, [], now + dt.timedelta(minutes=60)
        )
        assert key not in result

    def test_someone_elses_machine_not_ours(self, coordinator):
        """Machine going busy without a matching transaction is not ours."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        result = coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [], now + dt.timedelta(minutes=1)
        )
        assert key not in result

    def test_multiple_machines_independent(self, coordinator):
        """Each machine's 'ours' status is tracked independently."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key_a = (1000, 1)
        key_b = (1000, 2)

        coordinator._detect_our_machines(
            {key_a: _idle(1000, 1), key_b: _idle(1000, 2)}, [], now
        )

        tx_a = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        result = coordinator._detect_our_machines(
            {key_a: _busy(1000, 1), key_b: _busy(1000, 2)},
            [tx_a],
            now + dt.timedelta(minutes=1),
        )
        assert key_a in result
        assert key_b not in result

    def test_reservation_with_transaction_marks_ours(self, coordinator):
        """Reserved machine should be 'ours' when a matching transaction is seen.

        This reservation state is still based on an unverified payload shape.
        """
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        tx = TransactionDTOFactory.build(laundry_number=1000, machine_number=1)
        coordinator._detect_our_machines({key: _idle(1000, 1)}, [tx], now)
        result = coordinator._detect_our_machines(
            {key: _reserved(1000, 1)}, [], now + dt.timedelta(minutes=2)
        )
        assert key in result

    def test_reservation_without_transaction_not_ours(self, coordinator):
        """Reserved machine with no matching transaction is not ours.

        This reservation state is still based on an unverified payload shape.
        """
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        result = coordinator._detect_our_machines(
            {key: _reserved(1000, 1)}, [], now + dt.timedelta(minutes=1)
        )
        assert key not in result

    def test_previous_text_statuses_updated(self, coordinator):
        """Internal text status tracking is updated each call."""
        now = dt.datetime(2026, 1, 1, 12, 0, 0)
        key = (1000, 1)

        coordinator._detect_our_machines({key: _idle(1000, 1)}, [], now)
        assert coordinator._previous_text_statuses[key] == MachineTextStatus.Idle

        coordinator._detect_our_machines(
            {key: _busy(1000, 1)}, [], now + timedelta(minutes=1)
        )
        assert coordinator._previous_text_statuses[key] == MachineTextStatus.Running


@pytest.mark.asyncio
async def test_poll_cooldown_uses_poll_start_timestamp(coordinator):
    """A slow startup refresh should not delay the first scheduled poll."""
    first = MieleLogicData(balance=1.0, currency="DKK")
    second = MieleLogicData(balance=2.0, currency="DKK")
    coordinator.data = first
    coordinator._do_update = AsyncMock(side_effect=[first, second])
    coordinator._monotonic_time = MagicMock(side_effect=[0.0, 60.0])

    assert await coordinator._async_update_data() == first
    assert coordinator._poll_cooldown_until == 30.0
    assert await coordinator._async_update_data() == second
    assert coordinator._do_update.await_count == 2


@pytest.mark.asyncio
async def test_poll_cooldown_skips_back_to_back_refreshes(coordinator):
    """Refreshes inside the cooldown window should reuse cached data."""
    data = MieleLogicData(balance=1.0, currency="DKK")
    coordinator.data = data
    coordinator._do_update = AsyncMock(return_value=data)
    coordinator._monotonic_time = MagicMock(side_effect=[100.0, 110.0])

    assert await coordinator._async_update_data() == data
    assert await coordinator._async_update_data() == data
    assert coordinator._do_update.await_count == 1


@pytest.mark.asyncio
async def test_poll_cooldown_skip_is_logged(coordinator, caplog):
    """Cooldown skips should emit a debug log entry."""
    data = MieleLogicData(balance=1.0, currency="DKK")
    coordinator.data = data
    coordinator._do_update = AsyncMock(return_value=data)
    coordinator._monotonic_time = MagicMock(side_effect=[100.0, 110.0])

    with caplog.at_level("DEBUG"):
        await coordinator._async_update_data()
        await coordinator._async_update_data()

    assert "Skipping poll request: cooldown active for 20.0s more" in caplog.text


@pytest.mark.asyncio
async def test_laundry_states_result_text_is_logged(coordinator, caplog):
    """LaundryStatesResponseDTO.result_text should be visible in debug logs."""
    coordinator.client.details = AsyncMock(
        return_value=DetailsResponseDTOFactory.build(
            laundry_numbers=[1000, 1001], size=2
        )
    )
    coordinator.client.laundry_states = AsyncMock(
        side_effect=[
            LaundryStatesResponseDTOFactory.build(
                laundry_number=1000,
                size=1,
                result_text="Push",
            ),
            LaundryStatesResponseDTOFactory.build(
                laundry_number=1001,
                size=1,
                result_text="",
            ),
        ]
    )
    coordinator.client.transactions = AsyncMock(
        return_value=TransactionResponseDTOFactory.build(size=0)
    )

    with caplog.at_level("DEBUG"):
        await coordinator._do_update()

    assert "Laundry 1000 states fetched: 1 machines, result_text='Push'" in caplog.text
    assert "Laundry 1001 states fetched: 1 machines, result_text=''" in caplog.text
