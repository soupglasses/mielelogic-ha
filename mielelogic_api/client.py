"""Async application client for the MieleLogic HTTP API."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import ssl
import time
from typing import Any, AsyncGenerator

import httpx

from ._api import MieleLogicApiConfig, MieleLogicApiRoutes
from ._version import __version__
from .dto import (
    DetailsResponseDTO,
    LaundryStatesResponseDTO,
    ReservationReceiptResponseDTO,
    ReservationsResponseDTO,
    TimetableResponseDTO,
    TransactionResponseDTO,
    VersionResponseDTO,
)
from .exceptions import (
    MieleLogicAuthError,
    MieleLogicConnectionError,
)

_AUTH_STATUS_CODES = {401, 403}
_COMPATIBLE_VERSION = (7, 60, 9007, 21793)
_TOKEN_EXPIRY_MARGIN = 30  # seconds before expiry to refresh
_PUSH_RETRY_DELAY = 1.0
_RECEIPT_POLL_INTERVAL = 1.0
_RECEIPT_POLL_TIMEOUT = 10.0

LOGGER = logging.getLogger(__name__)


class _AsyncOAuth2Auth(httpx.Auth):
    """Async OAuth2 resource owner password credentials auth for httpx."""

    def __init__(
        self,
        token_url: str,
        username: str,
        password: str,
        client_id: str,
        scope: str,
        ssl_context: ssl.SSLContext,
    ) -> None:
        self._token_url = token_url
        self._data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "client_id": client_id,
            "scope": scope,
        }
        self._ssl_context = ssl_context
        self._token: str | None = None
        self._expires_at: float = 0.0

    def _is_expired(self) -> bool:
        return time.monotonic() >= self._expires_at - _TOKEN_EXPIRY_MARGIN

    async def _fetch_token(self) -> None:
        async with httpx.AsyncClient(verify=self._ssl_context) as client:
            response = await client.post(self._token_url, data=self._data)
            response.raise_for_status()
            payload = response.json()
        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 3600))
        self._expires_at = time.monotonic() + expires_in

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        if self._token is None or self._is_expired():
            await self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class MieleLogicClient:
    """Async API client for MieleLogic.

    Usage::

        async with MieleLogicClient(username, password, scope="DA") as client:
            details = await client.details()
            states = await client.laundry_states(details.accessible_laundries[0].laundry_number)
    """

    def __init__(
        self,
        username: str,
        password: str,
        scope: str,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._api_config = MieleLogicApiConfig(scope=scope)
        self._routes = MieleLogicApiRoutes(self._api_config)
        self._headers = {
            "user-agent": f"mielelogic-ha/{__version__}",
            "accept": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }
        self._ssl_context = (
            ssl_context if ssl_context is not None else ssl.create_default_context()
        )
        self._auth = _AsyncOAuth2Auth(
            token_url=self._api_config.token_url,
            username=username,
            password=password,
            client_id=self._api_config.client_id,
            scope=scope,
            ssl_context=self._ssl_context,
        )
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize connection and fetch server affinity cookies."""
        try:
            async with httpx.AsyncClient(
                auth=self._auth,
                headers=self._headers,
                verify=self._ssl_context,
                timeout=5,
            ) as client:
                response = await client.options(self._routes.account_details)
                if response.status_code in _AUTH_STATUS_CODES:
                    raise MieleLogicAuthError("Invalid credentials")
                cookies = response.cookies
        except httpx.HTTPError as err:
            raise MieleLogicConnectionError(str(err)) from err

        self._client = httpx.AsyncClient(
            auth=self._auth,
            headers=self._headers,
            cookies=cookies,
            verify=self._ssl_context,
            timeout=15,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> MieleLogicClient:
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def details(self) -> DetailsResponseDTO:
        """Get account details and accessible laundries."""
        data = await self._request_json("GET", self._routes.account_details)
        return DetailsResponseDTO(**data)

    async def laundry_states(self, laundry_number: int) -> LaundryStatesResponseDTO:
        """Get machine states for a laundry facility."""
        states = await self._fetch_laundry_states_once(laundry_number)
        if states.result_text != "Push":
            return states

        LOGGER.debug(
            "Laundry %s returned Push result_text; treating payload as transient "
            "and retrying in %.1fs",
            laundry_number,
            _PUSH_RETRY_DELAY,
        )
        await asyncio.sleep(_PUSH_RETRY_DELAY)
        retry = await self._fetch_laundry_states_once(laundry_number)
        if retry.result_text:
            LOGGER.warning(
                "Laundry %s retry after Push still returned result_text=%r",
                laundry_number,
                retry.result_text,
            )
        return retry

    async def transactions(
        self, from_: dt.datetime, to_: dt.datetime
    ) -> TransactionResponseDTO:
        """Get account transactions within a date range."""
        data = await self._request_json(
            "GET",
            self._routes.transactions,
            params={
                "dateFrom": from_.strftime("%Y-%m-%d-%H"),
                "dateTo": to_.strftime("%Y-%m-%d-%H"),
            },
        )
        return TransactionResponseDTO(**data)

    async def reservations(self, laundry_number: int) -> ReservationsResponseDTO:
        """Get user's reservations for a laundry facility."""
        data = await self._request_json(
            "GET", self._routes.reservations(laundry_number)
        )
        return ReservationsResponseDTO(**data)

    async def timetable(self, laundry_number: int) -> TimetableResponseDTO:
        """Get machine timetables for a laundry facility."""
        data = await self._request_json("GET", self._routes.timetable(laundry_number))
        return TimetableResponseDTO(**data)

    async def create_reservation(
        self,
        laundry_number: int,
        machine_number: int,
        start: dt.datetime,
        end: dt.datetime,
    ) -> ReservationReceiptResponseDTO:
        """Create a reservation and poll until confirmed."""
        await self._request_json(
            "PUT",
            self._routes.reservations_base,
            json={
                "MachineNumber": machine_number,
                "LaundryNumber": str(laundry_number),
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
        )
        return await self._poll_reservation_receipt(laundry_number)

    async def delete_reservation(
        self,
        laundry_number: int,
        machine_number: int,
        start: dt.datetime,
        end: dt.datetime,
    ) -> ReservationReceiptResponseDTO:
        """Delete a reservation and poll until confirmed."""
        await self._request_json(
            "DELETE",
            self._routes.reservations_base,
            params={
                "MachineNumber": machine_number,
                "LaundryNumber": laundry_number,
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
        )
        return await self._poll_reservation_receipt(laundry_number)

    async def _poll_reservation_receipt(
        self,
        laundry_number: int,
        *,
        timeout: float = _RECEIPT_POLL_TIMEOUT,
        interval: float = _RECEIPT_POLL_INTERVAL,
    ) -> ReservationReceiptResponseDTO:
        """Poll receipt endpoint until ResultText leaves 'InQueue'."""
        deadline = time.monotonic() + timeout
        while True:
            data = await self._request_json(
                "GET", self._routes.reservation_receipt(laundry_number)
            )
            receipt = ReservationReceiptResponseDTO(**data)
            if receipt.result_text != "InQueue":
                return receipt
            if time.monotonic() >= deadline:
                raise MieleLogicConnectionError(
                    f"Reservation receipt polling timed out after {timeout}s "
                    f"(still InQueue)"
                )
            await asyncio.sleep(interval)

    async def version(self) -> VersionResponseDTO:
        """Get API version information."""
        data = await self._request_json("GET", self._routes.version)
        return VersionResponseDTO(**data)

    async def _fetch_laundry_states_once(
        self, laundry_number: int
    ) -> LaundryStatesResponseDTO:
        data = await self._request_json(
            "GET", self._routes.laundry_states(laundry_number)
        )
        return LaundryStatesResponseDTO(**data)

    async def check_version(self) -> bool:
        """Check if the API version is compatible."""
        version = await self.version()
        return (
            version.major,
            version.minor,
            version.build,
            version.revision,
        ) <= _COMPATIBLE_VERSION

    def _ensure_connected(self) -> httpx.AsyncClient:
        if self._client is None:
            msg = (
                "Client not connected. Call connect() or use as async context manager."
            )
            raise RuntimeError(msg)
        return self._client

    async def _request_json(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Make an HTTP request and decode the JSON payload."""
        client = self._ensure_connected()
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as err:
            self._raise_for_status(
                err, invalid_credentials_message="Authentication failed"
            )
        except httpx.HTTPError as err:
            raise MieleLogicConnectionError(str(err)) from err
        except Exception as err:
            raise MieleLogicConnectionError(f"Unknown error: {err}") from err
        raise AssertionError("unreachable")

    def _raise_for_status(
        self,
        err: httpx.HTTPStatusError,
        *,
        invalid_credentials_message: str,
    ) -> None:
        if err.response.status_code in _AUTH_STATUS_CODES:
            raise MieleLogicAuthError(invalid_credentials_message) from err
        raise MieleLogicConnectionError(f"HTTP {err.response.status_code}") from err
