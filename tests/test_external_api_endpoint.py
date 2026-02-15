from mielelogic_ha import MieleLogic

import datetime
import pytest


@pytest.mark.network
def test_external_api_endpoint_details(mielelogic: MieleLogic):
    assert mielelogic.details().result_ok


@pytest.mark.network
def test_parse_endpoint_laundry_states(mielelogic: MieleLogic):
    details = mielelogic.details()
    laundry_states = [
        mielelogic.laundry_states(laundry.laundry_number)
        for laundry in details.accessible_laundries
    ]

    assert all(laundry_state.result_ok for laundry_state in laundry_states)


@pytest.mark.network
def test_external_api_endpoint_transactions(mielelogic: MieleLogic):
    assert mielelogic.transactions(
        from_=datetime.datetime.now() - datetime.timedelta(days=7),
        to_=datetime.datetime.now(),
    ).result_ok


@pytest.mark.network
def test_external_api_endpoint_version(mielelogic: MieleLogic):
    assert mielelogic.version().result_ok
