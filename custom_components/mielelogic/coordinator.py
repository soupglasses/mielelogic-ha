"""DataUpdateCoordinator for MieleLogic."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from mielelogic_api import (
    MieleLogicAuthError,
    MieleLogicClient,
    MieleLogicError,
)
from mielelogic_api.dto import (
    LaundryDTO,
    MachineStateDTO,
    MachineTextStatus,
    TransactionDTO,
)

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_TX_WINDOW = dt.timedelta(minutes=10)
_OUR_MACHINE_THRESHOLD = dt.timedelta(minutes=5)
_MIN_POLL_GAP = (
    30.0  # seconds — prevents back-to-back polls when update requests cluster
)


@dataclass
class MieleLogicData:
    """Processed data from a coordinator update."""

    laundries: dict[int, LaundryDTO] = field(default_factory=dict)
    machine_states: dict[tuple[int, int], MachineStateDTO] = field(default_factory=dict)
    our_machines: set[tuple[int, int]] = field(default_factory=set)
    """Keys of machines started or reserved by us within the current session.

    Use machine_text_status on the MachineStateDTO to distinguish running from reserved:
    - TimedRun + in our_machines  → "running"
    - Reserved + in our_machines  → "reserved" (by us)
    - TimedRun + not in our_machines → "busy" (someone else's)
    - Reserved + not in our_machines → "reserved_other"
    """
    balance: float = 0.0
    currency: str = ""


def _tx_key(tx: TransactionDTO) -> tuple:
    """Create a hashable key for a transaction to detect duplicates."""
    return (tx.laundry_number, tx.machine_number, tx.transaction_time, tx.amount)


class MieleLogicCoordinator(DataUpdateCoordinator[MieleLogicData]):
    """Coordinator that polls MieleLogic API for all entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MieleLogicClient,
        update_interval: dt.timedelta | None = None,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self._update_lock = asyncio.Lock()

        # State tracking for "ours" detection
        self._previous_text_statuses: dict[tuple[int, int], MachineTextStatus] = {}
        self._machine_busy_since: dict[tuple[int, int], dt.datetime] = {}
        self._recent_tx_for_machine: dict[tuple[int, int], dt.datetime] = {}
        self._seen_tx_keys: set[tuple] = set()
        self._our_machines: set[tuple[int, int]] = set()
        self._poll_cooldown_until: float | None = None

    def _monotonic_time(self) -> float:
        """Return the coordinator's monotonic clock."""
        return self.hass.loop.time()

    def _detect_our_machines(
        self,
        current_states: dict[tuple[int, int], MachineStateDTO],
        new_transactions: list[TransactionDTO],
        now: dt.datetime,
    ) -> set[tuple[int, int]]:
        """Update "ours" tracking based on state transitions and recent transactions.

        A machine is marked as "ours" when:
        - A new transaction appears for it within _TX_WINDOW, AND
        - It transitioned from Idle to a non-idle state within _OUR_MACHINE_THRESHOLD of
          that transaction (covers both buying wash time and making a reservation).

        A machine is cleared from "ours" when it returns to Idle (no transaction check
        needed — the machine finishing is unambiguous).
        """
        # Track Idle → non-idle transitions using text status for full granularity
        for key, machine in current_states.items():
            text_status = machine.machine_text_status
            prev = self._previous_text_statuses.get(key)

            if prev == MachineTextStatus.Idle and text_status != MachineTextStatus.Idle:
                # Machine just became active (running or reserved)
                self._machine_busy_since[key] = now
                tx_time = self._recent_tx_for_machine.get(key)
                if tx_time and (now - tx_time) <= _OUR_MACHINE_THRESHOLD:
                    self._our_machines.add(key)

            elif text_status == MachineTextStatus.Idle:
                # Machine finished or reservation expired — clear "ours" status
                self._our_machines.discard(key)
                self._machine_busy_since.pop(key, None)
                self._recent_tx_for_machine.pop(key, None)

        # Process new transactions: record time and check if machine is already active
        for tx in new_transactions:
            key = (tx.laundry_number, tx.machine_number)
            self._recent_tx_for_machine[key] = now
            busy_since = self._machine_busy_since.get(key)
            if busy_since and (now - busy_since) <= _OUR_MACHINE_THRESHOLD:
                self._our_machines.add(key)

        self._previous_text_statuses = {
            k: v.machine_text_status for k, v in current_states.items()
        }
        return self._our_machines.copy()

    async def _async_update_data(self) -> MieleLogicData:
        """Fetch all data from MieleLogic API."""
        if self._update_lock.locked():
            LOGGER.debug("Skipping poll request: previous request still in progress")
            return self.data
        now = self._monotonic_time()
        cooldown_until = self._poll_cooldown_until
        if cooldown_until is not None and now < cooldown_until:
            LOGGER.debug(
                "Skipping poll request: cooldown active for %.1fs more",
                cooldown_until - now,
            )
            return self.data
        async with self._update_lock:
            self._poll_cooldown_until = now + _MIN_POLL_GAP
            return await self._do_update()

    async def _do_update(self) -> MieleLogicData:
        """Perform the actual API fetch."""
        try:
            details = await self.client.details()

            laundries = {
                facility.laundry_number: facility
                for facility in details.accessible_laundries
            }

            all_machine_states: dict[tuple[int, int], MachineStateDTO] = {}
            for laundry_number in laundries:
                states_resp = await self.client.laundry_states(laundry_number)
                LOGGER.debug(
                    "Laundry %s states fetched: %s machines, result_text=%r",
                    laundry_number,
                    len(states_resp.machine_states),
                    states_resp.result_text,
                )
                for machine in states_resp.machine_states:
                    key = (machine.laundry_number, machine.machine_number)
                    all_machine_states[key] = machine

            now = dt.datetime.now()
            tx_resp = await self.client.transactions(from_=now - _TX_WINDOW, to_=now)

            # Find new transactions (unseen since last poll)
            current_tx_keys = {_tx_key(tx) for tx in tx_resp.transactions}
            new_tx_keys = current_tx_keys - self._seen_tx_keys
            self._seen_tx_keys = current_tx_keys
            new_txs = [tx for tx in tx_resp.transactions if _tx_key(tx) in new_tx_keys]

            our_machines = self._detect_our_machines(all_machine_states, new_txs, now)

            balance = 0.0
            currency = ""
            if details.cards:
                balance = details.cards[0].account_balance
                currency = details.cards[0].currency

            return MieleLogicData(
                laundries=laundries,
                machine_states=all_machine_states,
                our_machines=our_machines,
                balance=balance,
                currency=currency,
            )

        except MieleLogicAuthError as err:
            raise ConfigEntryAuthFailed from err
        except MieleLogicError as err:
            raise UpdateFailed(f"Error communicating with MieleLogic: {err}") from err


type MieleLogicConfigEntry = ConfigEntry[MieleLogicCoordinator]
