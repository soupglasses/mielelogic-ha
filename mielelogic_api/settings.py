"""Credential loading for local tooling."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class MieleLogicCredentials(BaseModel):
    """Validated MieleLogic client credentials."""

    username: SecretStr
    password: SecretStr
    scope: str

    def as_client_kwargs(self) -> dict[str, str]:
        """Return plain string credentials for client construction."""
        return {
            "username": self.username.get_secret_value(),
            "password": self.password.get_secret_value(),
            "scope": self.scope,
        }


class EnvironmentCredentials(BaseSettings):
    """Credentials loaded from environment variables or repo `.env`."""

    username: SecretStr
    password: SecretStr
    scope: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="mielelogic_",
    )

    def to_credentials(self) -> MieleLogicCredentials:
        """Convert settings model to reusable credentials."""
        return MieleLogicCredentials.model_validate(self.model_dump())


def load_environment_credentials() -> MieleLogicCredentials | None:
    """Load credentials from the configured environment."""
    try:
        return EnvironmentCredentials().to_credentials()
    except ValidationError:
        return None
