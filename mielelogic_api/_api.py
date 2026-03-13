"""Internal API configuration and route construction."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MieleLogicApiConfig:
    """Immutable API configuration for a scoped client."""

    scope: str
    base_url: str = "https://api.mielelogic.com/v7"
    token_url: str = "https://sec.mielelogic.com/v7/token"
    client_id: str = "YV1ZAQ7BTE9IT2ZBZXLJ"
    language: str = "en"


@dataclass(frozen=True, slots=True)
class MieleLogicApiRoutes:
    """Route builder for MieleLogic resources."""

    config: MieleLogicApiConfig

    @property
    def account_details(self) -> str:
        return f"{self.config.base_url}/accounts/Details"

    @property
    def transactions(self) -> str:
        return f"{self.config.base_url}/accounts/transactions"

    @property
    def version(self) -> str:
        return f"{self.config.base_url}/Version"

    @property
    def reservations_base(self) -> str:
        return f"{self.config.base_url}/reservations"

    def reservations(self, laundry_number: int) -> str:
        return f"{self.config.base_url}/reservations?laundry={laundry_number}"

    def reservation_receipt(self, laundry_number: int) -> str:
        return f"{self.config.base_url}/reservations/receipt?laundry={laundry_number}"

    def timetable(self, laundry_number: int) -> str:
        return (
            f"{self.config.base_url}/country/{self.config.scope}"
            f"/laundry/{laundry_number}/timetable"
        )

    def laundry_states(self, laundry_number: int) -> str:
        return (
            f"{self.config.base_url}/Country/{self.config.scope}"
            f"/Laundry/{laundry_number}/laundrystates"
            f"?language={self.config.language}"
        )
