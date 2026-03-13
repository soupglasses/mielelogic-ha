from mielelogic_api import MieleLogicClient, MieleLogicConnectionError

import pytest
import pytest_asyncio
import pytest_socket
from polyfactory.pytest_plugin import register_fixture
from pydantic import SecretStr

from mielelogic_api.settings import MieleLogicCredentials, load_environment_credentials
from tests.support.factories import (
    LaundrySettingsDTOFactory,
    CardDTOFactory,
    LaundryDTOFactory,
    DetailsResponseDTOFactory,
    MachineStateDTOFactory,
    LaundryStatesResponseDTOFactory,
    ReservationDTOFactory,
    ReservationsResponseDTOFactory,
    ReservationReceiptResponseDTOFactory,
    TimeSlotDTOFactory,
    MachineTimeTableDTOFactory,
    TimetableResponseDTOFactory,
    VersionResponseDTOFactory,
    TransactionDTOFactory,
    TransactionResponseDTOFactory,
)

register_fixture(LaundrySettingsDTOFactory)
register_fixture(CardDTOFactory)
register_fixture(LaundryDTOFactory)
register_fixture(DetailsResponseDTOFactory)
register_fixture(MachineStateDTOFactory)
register_fixture(LaundryStatesResponseDTOFactory)
register_fixture(ReservationDTOFactory)
register_fixture(ReservationsResponseDTOFactory)
register_fixture(ReservationReceiptResponseDTOFactory)
register_fixture(TimeSlotDTOFactory)
register_fixture(MachineTimeTableDTOFactory)
register_fixture(TimetableResponseDTOFactory)
register_fixture(VersionResponseDTOFactory)
register_fixture(TransactionDTOFactory)
register_fixture(TransactionResponseDTOFactory)


@pytest.fixture(scope="session")
def secret_settings() -> MieleLogicCredentials:
    settings = load_environment_credentials()
    if settings is None:
        pytest.skip("Missing required secrets: username, password, scope")
    return settings


@pytest.fixture(scope="session")
def username(secret_settings: MieleLogicCredentials) -> SecretStr:
    return secret_settings.username


@pytest.fixture(scope="session")
def password(secret_settings: MieleLogicCredentials) -> SecretStr:
    return secret_settings.password


@pytest.fixture(scope="session")
def scope(secret_settings: MieleLogicCredentials) -> str:
    return secret_settings.scope


@pytest_asyncio.fixture
async def mielelogic(
    username: SecretStr, password: SecretStr, scope: str
) -> MieleLogicClient:
    client = MieleLogicClient(
        username=username.get_secret_value(),
        password=password.get_secret_value(),
        scope=scope,
    )
    try:
        await client.connect()
    except MieleLogicConnectionError as exc:
        pytest.skip(f"Network test unavailable: {exc}")
    yield client
    await client.close()


def pytest_addoption(parser):
    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="run tests marked as requiring network access",
    )


@pytest.fixture(autouse=True)
def _enable_socket_for_network_tests(request):
    # pytest-homeassistant-custom-component calls socket_allow_hosts(["127.0.0.1"])
    # then disable_socket() in its pytest_runtest_setup hook for every test.
    # socket_allow_hosts() patches _true_socket.connect = guarded_connect directly
    # on the class, so enable_socket() (which only restores socket.socket = _true_socket)
    # leaves guarded_connect in place. _remove_restrictions() restores both, but
    # enable_socket() not calling it is arguably a bug in pytest-socket.
    if request.node.get_closest_marker("network"):
        pytest_socket._remove_restrictions()


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network"):
        return
    for item in items:
        if item.get_closest_marker("network"):
            item.add_marker(pytest.mark.skip(reason="need --network option to run"))
