from mielelogic_api import MieleLogicClient

import datetime
import pytest


@pytest.mark.network
async def test_external_api_endpoint_details(mielelogic: MieleLogicClient):
    assert (await mielelogic.details()).result_ok


@pytest.mark.network
async def test_parse_endpoint_laundry_states(mielelogic: MieleLogicClient):
    details = await mielelogic.details()
    laundry_states = [
        await mielelogic.laundry_states(laundry.laundry_number)
        for laundry in details.accessible_laundries
    ]

    assert all(laundry_state.result_ok for laundry_state in laundry_states)


@pytest.mark.network
async def test_external_api_endpoint_transactions(mielelogic: MieleLogicClient):
    assert (
        await mielelogic.transactions(
            from_=datetime.datetime.now() - datetime.timedelta(days=7),
            to_=datetime.datetime.now(),
        )
    ).result_ok


@pytest.mark.network
async def test_external_api_endpoint_version(mielelogic: MieleLogicClient):
    assert (await mielelogic.version()).result_ok
