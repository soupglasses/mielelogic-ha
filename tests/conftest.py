from mielelogic_ha import MieleLogic

import pytest
from polyfactory.pytest_plugin import register_fixture
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, ValidationError

from tests.factories import (
    LaundrySettingsDTOFactory,
    CardDTOFactory,
    LaundryDTOFactory,
    DetailsResponseDTOFactory,
    MachineStateDTOFactory,
    LaundryStatesResponseDTOFactory,
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
register_fixture(VersionResponseDTOFactory)
register_fixture(TransactionDTOFactory)
register_fixture(TransactionResponseDTOFactory)


class TestSecretSettings(BaseSettings):
    username: SecretStr
    password: SecretStr
    scope: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="mielelogic_",
    )


@pytest.fixture(scope="session")
def secret_settings() -> TestSecretSettings:
    try:
        return TestSecretSettings()  # type: ignore
    except ValidationError as e:
        missing = [str(err["loc"][0]) for err in e.errors()]
        pytest.skip(f"Missing required secrets: {', '.join(missing)}")


@pytest.fixture(scope="session")
def username(secret_settings: TestSecretSettings) -> SecretStr:
    return secret_settings.username


@pytest.fixture(scope="session")
def password(secret_settings: TestSecretSettings) -> SecretStr:
    return secret_settings.password


@pytest.fixture(scope="session")
def scope(secret_settings: TestSecretSettings) -> str:
    return secret_settings.scope


@pytest.fixture(scope="session")
def mielelogic(username: SecretStr, password: SecretStr, scope: str) -> MieleLogic:
    return MieleLogic(username=username, password=password, scope=scope)


def pytest_configure(config):
    config.addinivalue_line("markers", "network: mark test as requiring network access")
