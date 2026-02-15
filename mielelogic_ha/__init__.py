import datetime as dt
from functools import cache
import importlib.metadata
from typing import Any, ClassVar

import httpx
import httpx_auth
from pydantic import BaseModel, PrivateAttr, SecretStr

from .dto import (
    DetailsResponseDTO,
    LaundryStatesResponseDTO,
    TransactionResponseDTO,
    VersionResponseDTO,
)

__version__ = importlib.metadata.version(__name__)


class MieleLogic(BaseModel):
    HEADERS: ClassVar = {
        "user-agent": f"mielelogic-hass/{__version__}",
        "accept": "application/json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    URL_BASE: ClassVar = "https://api.mielelogic.com/v7"
    CLIENT_ID: ClassVar = "YV1ZAQ7BTE9IT2ZBZXLJ"

    username: SecretStr
    password: SecretStr
    scope: str

    _auth: httpx_auth.OAuth2ResourceOwnerPasswordCredentials = PrivateAttr()
    _client: httpx.Client = PrivateAttr()
    _cookies: httpx.Cookies = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        self._auth = httpx_auth.OAuth2ResourceOwnerPasswordCredentials(
            token_url="https://sec.mielelogic.com/v7/token",
            username=self.username.get_secret_value(),
            password=self.password.get_secret_value(),
            client_id=self.CLIENT_ID,
            scope=self.scope,
        )

        # Fetch cookies for server affinity
        with httpx.Client(auth=self._auth, headers=self.HEADERS, timeout=5) as client:
            r = client.options(f"{self.URL_BASE}/accounts/Details")
            self._cookies = r.cookies

        self._client = httpx.Client(
            auth=self._auth, headers=self.HEADERS, cookies=self._cookies, timeout=15
        )

    def __del__(self):
        self._client.close()

    def laundry_states(self, laundry_number: int) -> LaundryStatesResponseDTO:
        url = f"{self.URL_BASE}/Country/{self.scope}/Laundry/{laundry_number}/laundrystates?language=en"
        response = self._client.get(url).json()
        return LaundryStatesResponseDTO(**response)

    def details(self) -> DetailsResponseDTO:
        url = f"{self.URL_BASE}/accounts/Details"
        response = self._client.get(url).json()
        return DetailsResponseDTO(**response)

    def transactions(
        self, from_: dt.datetime, to_: dt.datetime
    ) -> TransactionResponseDTO:
        url = f"{self.URL_BASE}/accounts/transactions"
        response = self._client.get(
            url,
            params={
                "dateFrom": from_.strftime("%Y-%m-%d-%H"),
                "dateTo": to_.strftime("%Y-%m-%d-%H"),
            },
        ).json()
        return TransactionResponseDTO(**response)

    def check_version(self):
        version = self.version()
        version_tuple = (
            version.major,
            version.minor,
            version.build,
            version.revision,
        )
        return version_tuple <= (7, 60, 9007, 21793)

    def version(self) -> VersionResponseDTO:
        url = f"{self.URL_BASE}/Version"
        response = self._client.get(url).json()
        return VersionResponseDTO(**response)


@cache
def get_miele_logic() -> MieleLogic:
    return MieleLogic(
        username=SecretStr("example"),
        password=SecretStr("example"),
        scope="DA",
    )


def test() -> tuple[
    MieleLogic,
    DetailsResponseDTO,
    list[LaundryStatesResponseDTO],
    TransactionResponseDTO,
]:
    mielelogic = get_miele_logic()

    details = mielelogic.details()
    laundry_states = [
        mielelogic.laundry_states(laundry.number)
        for laundry in details.accessible_laundries
    ]
    transactions = mielelogic.transactions(
        from_=dt.datetime.now() - dt.timedelta(days=7), to_=dt.datetime.now()
    )

    return mielelogic, details, laundry_states, transactions
