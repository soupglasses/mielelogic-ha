"""Tests for the MieleLogic config flow."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.data_entry_flow import FlowResultType

from mielelogic_api import MieleLogicAuthError, MieleLogicConnectionError

from custom_components.mielelogic.config_flow import MieleLogicFlowHandler


async def test_user_flow_success():
    """Test a successful config flow."""
    flow = MieleLogicFlowHandler()
    flow.hass = Mock()
    flow.context = {}

    result_data = {
        "username": "testuser",
        "password": "testpass",
        "scope": "DA",
    }

    with (
        patch.object(flow, "_test_credentials", AsyncMock()),
        patch.object(flow, "async_set_unique_id", AsyncMock()) as async_set_unique_id,
        patch.object(flow, "_abort_if_unique_id_configured") as abort_if_unique_id,
    ):
        result = await flow.async_step_user(result_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "testuser"
    assert result["data"]["username"] == "testuser"
    assert result["data"]["scope"] == "DA"
    async_set_unique_id.assert_awaited_once_with("testuser")
    abort_if_unique_id.assert_called_once_with()


async def test_user_flow_auth_error():
    """Test config flow with invalid credentials."""
    flow = MieleLogicFlowHandler()
    flow.hass = Mock()
    flow.context = {}

    with patch.object(
        flow,
        "_test_credentials",
        AsyncMock(side_effect=MieleLogicAuthError("bad creds")),
    ):
        result = await flow.async_step_user(
            {
                "username": "testuser",
                "password": "badpass",
                "scope": "DA",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}


async def test_user_flow_connection_error():
    """Test config flow with connection error."""
    flow = MieleLogicFlowHandler()
    flow.hass = Mock()
    flow.context = {}

    with patch.object(
        flow,
        "_test_credentials",
        AsyncMock(side_effect=MieleLogicConnectionError("timeout")),
    ):
        result = await flow.async_step_user(
            {
                "username": "testuser",
                "password": "testpass",
                "scope": "DA",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "connection"}


def test_manifest_requires_published_mielelogic_api_package():
    """The HA integration must depend on the published client library package."""
    manifest = json.loads(
        Path("custom_components/mielelogic/manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["requirements"] == ["mielelogic-api==1.0.0"]
