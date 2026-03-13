"""Unit tests for MieleLogic DTOs and factories."""

import re

import pytest

from mielelogic_api.dto import MachineKind, MachineStatus

from tests.support.factories import (
    DetailsResponseDTOFactory,
    LaundryDTOFactory,
    LaundryStatesResponseDTOFactory,
    MachineStateDTOFactory,
    ReservationsResponseDTOFactory,
    ReservationReceiptResponseDTOFactory,
    TimetableResponseDTOFactory,
    TransactionResponseDTOFactory,
    VersionResponseDTOFactory,
)


class TestDTOFactories:
    """Verify all factories produce valid DTOs."""

    def test_details_factory(self):
        details = DetailsResponseDTOFactory.build()
        assert details.result_ok
        assert len(details.accessible_laundries) >= 1
        assert len(details.cards) >= 1

    def test_laundry_states_factory(self):
        states = LaundryStatesResponseDTOFactory.build()
        assert states.result_ok
        assert len(states.machine_states) >= 1

    def test_machine_state_status_mapping(self):
        for color in range(4):
            machine = MachineStateDTOFactory.build(machine_color=color)
            assert machine.machine_status == MachineStatus(color)

    def test_machine_state_kind_mapping(self):
        for symbol in range(8):
            machine = MachineStateDTOFactory.build(machine_symbol=symbol)
            assert machine.machine_kind == MachineKind(symbol)

    def test_machine_state_factory_pairs_text1_and_text2(self):
        for _ in range(20):
            machine = MachineStateDTOFactory.build()
            if machine.text1 == "Idle":
                assert machine.text2 == " "
            elif machine.text1 == "Time left":
                assert re.fullmatch(r"\d+ min", machine.text2)
            elif machine.text1 == "Reserved until":
                assert re.fullmatch(r"\d{1,2}:\d{2}", machine.text2)
            else:
                pytest.fail(f"Unexpected text1 generated: {machine.text1!r}")

    def test_version_factory(self):
        version = VersionResponseDTOFactory.build()
        assert version.result_ok

    def test_reservations_factory(self):
        resp = ReservationsResponseDTOFactory.build()
        assert resp.result_ok
        assert len(resp.reservations) >= 1

    def test_reservation_receipt_factory(self):
        receipt = ReservationReceiptResponseDTOFactory.build()
        assert receipt.result_ok

    def test_timetable_factory(self):
        tt = TimetableResponseDTOFactory.build()
        assert tt.result_ok
        assert len(tt.machine_time_tables) >= 1
        for machine_tt in tt.machine_time_tables.values():
            assert len(machine_tt.time_table) >= 1

    def test_transaction_factory(self):
        tx_resp = TransactionResponseDTOFactory.build()
        assert tx_resp.result_ok
        assert len(tx_resp.transactions) >= 1

    def test_laundry_ordering(self):
        a = LaundryDTOFactory.build(laundry_number=100)
        b = LaundryDTOFactory.build(laundry_number=200)
        assert a < b

    def test_machine_state_ordering(self):
        a = MachineStateDTOFactory.build(
            laundry_number=100, group_number=0, machine_number=1
        )
        b = MachineStateDTOFactory.build(
            laundry_number=100, group_number=0, machine_number=2
        )
        assert a < b


class TestDTOValidation:
    """Test DTO validation rules."""

    def test_details_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            DetailsResponseDTOFactory.build(result_ok=False, result_text="Error")

    def test_laundry_states_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            LaundryStatesResponseDTOFactory.build(result_ok=False, result_text="Error")

    def test_version_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            VersionResponseDTOFactory.build(result_ok=False, result_text="Error")

    def test_reservations_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            ReservationsResponseDTOFactory.build(result_ok=False, result_text="Error")

    def test_timetable_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            TimetableResponseDTOFactory.build(result_ok=False, result_text="Error")

    def test_transaction_rejects_result_not_ok(self):
        with pytest.raises(ValueError, match="Invalid"):
            TransactionResponseDTOFactory.build(result_ok=False, result_text="Error")
