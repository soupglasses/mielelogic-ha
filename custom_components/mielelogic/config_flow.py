"""Config flow for MieleLogic."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.util.ssl import get_default_context

from mielelogic_api import (
    MieleLogicAuthError,
    MieleLogicClient,
    MieleLogicConnectionError,
    MieleLogicError,
)

from .const import CONF_SCOPE, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
        vol.Required(CONF_SCOPE, default="DA"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="DA", label="Denmark"),
                    selector.SelectOptionDict(value="NO", label="Norway"),
                ],
            ),
        ),
    }
)


class MieleLogicFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MieleLogic."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    scope=user_input[CONF_SCOPE],
                )
            except MieleLogicAuthError:
                errors["base"] = "auth"
            except MieleLogicConnectionError:
                errors["base"] = "connection"
            except MieleLogicError as exc:
                LOGGER.exception("Unexpected error during config flow: %s", exc)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def _test_credentials(self, username: str, password: str, scope: str) -> None:
        """Validate credentials by connecting and fetching details."""
        ssl_context = await self.hass.async_add_executor_job(get_default_context)
        client = MieleLogicClient(
            username=username,
            password=password,
            scope=scope,
            ssl_context=ssl_context,
        )
        async with client:
            await client.details()
