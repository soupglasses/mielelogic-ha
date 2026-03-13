"""Unit tests for the MieleLogicClient."""

import httpx
import pytest
import respx

from mielelogic_api import MieleLogicAuthError, MieleLogicClient
from tests.support.factories import (
    LaundryStatesResponseDTOFactory,
    ReservationsResponseDTOFactory,
    TimetableResponseDTOFactory,
)


def _mock_bootstrap(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("https://sec.mielelogic.com/v7/token").respond(
        200,
        json={
            "access_token": "token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )


class TestMieleLogicClient:
    """Test client construction and state."""

    def test_client_not_connected_raises(self):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        with pytest.raises(RuntimeError, match="not connected"):
            client._ensure_connected()

    def test_client_has_correct_headers(self):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        assert "mielelogic-ha" in client._headers["user-agent"]
        assert client._headers["accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_connect_allows_405_bootstrap_options(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )

        await client.connect()

        assert client._client is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_connect_raises_auth_error_for_401_bootstrap_options(
        self, respx_mock
    ):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            401
        )

        with pytest.raises(MieleLogicAuthError, match="Invalid credentials"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_laundry_states_retries_once_after_push(self, respx_mock, caplog):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        states_route = respx_mock.get(
            "https://api.mielelogic.com/v7/Country/DA/Laundry/1000/laundrystates?language=en"
        )
        states_route.side_effect = [
            httpx.Response(
                200,
                json=LaundryStatesResponseDTOFactory.build(
                    laundry_number=1000,
                    size=1,
                    result_text="Push",
                ).to_api(),
            ),
            httpx.Response(
                200,
                json=LaundryStatesResponseDTOFactory.build(
                    laundry_number=1000,
                    size=1,
                    result_text="",
                ).to_api(),
            ),
        ]

        await client.connect()
        try:
            with caplog.at_level("DEBUG"):
                result = await client.laundry_states(1000)
        finally:
            await client.close()

        assert states_route.call_count == 2
        assert result.result_text == ""
        assert (
            "Laundry 1000 returned Push result_text; treating payload as transient "
            "and retrying in 1.0s" in caplog.text
        )
        assert "retry after Push still returned result_text" not in caplog.text

    @pytest.mark.asyncio
    async def test_laundry_states_non_push_does_not_retry(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        states_route = respx_mock.get(
            "https://api.mielelogic.com/v7/Country/DA/Laundry/1000/laundrystates?language=en"
        ).respond(
            200,
            json=LaundryStatesResponseDTOFactory.build(
                laundry_number=1000,
                size=1,
                result_text="",
            ).to_api(),
        )

        await client.connect()
        try:
            result = await client.laundry_states(1000)
        finally:
            await client.close()

        assert states_route.call_count == 1
        assert result.result_text == ""

    @pytest.mark.asyncio
    async def test_reservations_get(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        expected = ReservationsResponseDTOFactory.build(laundry_number=1234, size=1)
        respx_mock.get(
            "https://api.mielelogic.com/v7/reservations?laundry=1234"
        ).respond(200, json=expected.to_api())

        await client.connect()
        try:
            result = await client.reservations(1234)
        finally:
            await client.close()

        assert result.result_ok
        assert len(result.reservations) == 1

    @pytest.mark.asyncio
    async def test_timetable_get(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        expected = TimetableResponseDTOFactory.build(size=2)
        respx_mock.get(
            "https://api.mielelogic.com/v7/country/DA/laundry/1234/timetable"
        ).respond(200, json=expected.to_api())

        await client.connect()
        try:
            result = await client.timetable(1234)
        finally:
            await client.close()

        assert result.result_ok
        assert len(result.machine_time_tables) == 2

    @pytest.mark.asyncio
    async def test_create_reservation_polls_receipt(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        respx_mock.put("https://api.mielelogic.com/v7/reservations").respond(
            200, json={"ResultText": "", "ResultOK": True}
        )
        receipt_route = respx_mock.get(
            "https://api.mielelogic.com/v7/reservations/receipt?laundry=1234"
        )
        receipt_route.side_effect = [
            httpx.Response(200, json={"ResultText": "InQueue", "ResultOK": True}),
            httpx.Response(200, json={"ResultText": "Created", "ResultOK": True}),
        ]

        await client.connect()
        try:
            import datetime as dt

            result = await client.create_reservation(
                1234, 1, dt.datetime(2025, 1, 1, 10, 0), dt.datetime(2025, 1, 1, 11, 30)
            )
        finally:
            await client.close()

        assert receipt_route.call_count == 2
        assert result.result_text == "Created"

    @pytest.mark.asyncio
    async def test_delete_reservation_polls_receipt(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        respx_mock.delete("https://api.mielelogic.com/v7/reservations").respond(
            200, json={"ResultText": "", "ResultOK": True}
        )
        receipt_route = respx_mock.get(
            "https://api.mielelogic.com/v7/reservations/receipt?laundry=1234"
        )
        receipt_route.side_effect = [
            httpx.Response(200, json={"ResultText": "InQueue", "ResultOK": True}),
            httpx.Response(200, json={"ResultText": "Created", "ResultOK": True}),
        ]

        await client.connect()
        try:
            import datetime as dt

            result = await client.delete_reservation(
                1234, 6, dt.datetime(2025, 1, 1, 10, 0), dt.datetime(2025, 1, 1, 11, 30)
            )
        finally:
            await client.close()

        assert receipt_route.call_count == 2
        assert result.result_text == "Created"

    @pytest.mark.asyncio
    async def test_create_reservation_receipt_immediate(self, respx_mock):
        client = MieleLogicClient(username="u", password="p", scope="DA")
        _mock_bootstrap(respx_mock)
        respx_mock.options("https://api.mielelogic.com/v7/accounts/Details").respond(
            405,
            headers={"set-cookie": "ARRAffinity=something"},
        )
        respx_mock.put("https://api.mielelogic.com/v7/reservations").respond(
            200, json={"ResultText": "", "ResultOK": True}
        )
        receipt_route = respx_mock.get(
            "https://api.mielelogic.com/v7/reservations/receipt?laundry=1234"
        ).respond(200, json={"ResultText": "Created", "ResultOK": True})

        await client.connect()
        try:
            import datetime as dt

            result = await client.create_reservation(
                1234, 1, dt.datetime(2025, 1, 1, 10, 0), dt.datetime(2025, 1, 1, 11, 30)
            )
        finally:
            await client.close()

        assert receipt_route.call_count == 1
        assert result.result_text == "Created"
