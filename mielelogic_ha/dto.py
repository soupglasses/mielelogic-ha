import datetime as dt
from enum import Enum
from functools import total_ordering
from typing import Optional, Self
from pydantic import BaseModel, Field, computed_field, model_validator, AliasChoices


class MachineKind(int, Enum):
    """Maps to MachineSymbol in /laundrystates."""

    Washer = 0
    Dryer = 1
    Mangler = 2
    Coffee = 3
    Shower = 4
    Spa = 5
    Sauna = 6
    Solarium = 7


class MachineStatus(int, Enum):
    """Maps to MachineColor in /laundrystates."""

    Closed = 0
    Idle = 1
    Busy = 2
    Disabled = 3


class LaundrySettingsDTO(BaseModel):
    """Laundry settings from /Details endpoint."""

    phone_number: str = Field(validation_alias="PhoneNumber", examples=["12345678"])
    language: str = Field(validation_alias="LaundryLanguage", examples=["da"])
    sms_mode_machine_enabled: bool = Field(
        validation_alias="LaundrySmsModeMachineEnabled"
    )
    sms_mode_reservation_enabled: bool = Field(
        validation_alias="LaundrySmsModeReservationEnabled"
    )
    sms_reservation_time: int = Field(
        validation_alias="LaundrySmsReservationTime", ge=0, examples=[60]
    )
    sms_mode_auto_receipt_enabled: bool = Field(
        validation_alias="LaundrySmsModeAutoReceiptEnabled"
    )
    sms_recipt_time: int = Field(
        validation_alias="LaundrySmsReceiptTime", ge=0, examples=[0]
    )


class CardDTO(BaseModel):
    """Card information from /Details endpoint."""

    card_issuer_number: int = Field(
        validation_alias="CardIssuerNumber", examples=[1000, 2000, 3000]
    )
    card_laundry_number: int = Field(
        validation_alias="CardLaundryNumber", examples=[123]
    )
    card_content: str = Field(
        validation_alias="CardContent", examples=["800001234567891"]
    )
    name: str = Field(validation_alias="Name", examples=["Nomen Nescio"])
    email: str = Field(validation_alias="Email", examples=["nn@example.com"])
    address: str = Field(
        validation_alias="Address", examples=["H.C. Andersens Boulevard 34, 1. th"]
    )
    city: str = Field(validation_alias="City", examples=["København V"])
    zip_code: str = Field(validation_alias="ZipCode", examples=["1553"])
    account_balance: float = Field(
        validation_alias=AliasChoices(
            "AccountBalance", "AccountBallance"
        ),  # API-side typo "Ballance"
        examples=[
            0,
            -10.0,
            -20.0,
            -30.0,
        ],
        description="current account balance given in 'currency'",
    )
    laundry_settings: LaundrySettingsDTO = Field(validation_alias="LaundrySettings")
    card_terminated: str = Field(
        validation_alias="CardTerminated", examples=["0001-01-01T00:00:00"]
    )
    account_type: int = Field(validation_alias="AccountType", ge=0, examples=[2])
    currency: str = Field(validation_alias="Currency", examples=["DKK"])
    message_to_user: str = Field(validation_alias="MessageToUser", examples=[""])
    message_expires: dt.datetime = Field(
        validation_alias="MessageExpires", examples=["1900-01-01T00:00:00"]
    )
    message_modified: dt.datetime = Field(
        validation_alias="MessageModified", examples=["1900-01-01T00:00:00"]
    )
    name_read_only: bool = Field(validation_alias="NameReadOnly")
    address_read_only: bool = Field(validation_alias="AddressReadOnly")
    email_confirmed: bool = Field(validation_alias="EmailConfirmed")
    phone_confirmed: bool = Field(validation_alias="PhoneConfirmed")


@total_ordering
class LaundryDTO(BaseModel):
    """Laundry facility information from /Details endpoint."""

    number: int = Field(
        validation_alias="LaundryNumber", ge=0
    )  # sent as str, treat as int.
    name: str = Field(validation_alias="Name", examples=["Nomen Nescio"])
    address: str = Field(
        validation_alias="Address", examples=["H.C. Andersens Boulevard 34"]
    )
    zip_code: str = Field(validation_alias="ZipCode", examples=["1553"])
    geo_latitude: float = Field(validation_alias="GeoLatitude", ge=0, le=90)
    geo_longitude: float = Field(validation_alias="GeoLongitude", ge=-180, le=180)

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self.number < other.number
        return NotImplemented


class DetailsResponseDTO(BaseModel):
    """Response from /Details endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK")
    result_text: str = Field(validation_alias="ResultText", examples=[""])

    apartment_number: str = Field(validation_alias="ApartmentNumber", examples=["0001"])
    cards: list[CardDTO] = Field(validation_alias="Cards")
    accessible_laundries: list[LaundryDTO] = Field(
        validation_alias="AccessibleLaundries"
    )

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


@total_ordering
class MachineStateDTO(BaseModel):
    """Machine state information from /laundrystates endpoint."""

    laundry_number: int = Field(validation_alias="LaundryNumber", ge=0)
    group_number: int = Field(
        validation_alias="GroupNumber",
        ge=0,
        description="Grouping of machines, may be used to signify different rooms or different kinds of machines",
        examples=[0, 1],
    )
    number: int = Field(validation_alias="MachineNumber", ge=0)
    unit_name: str = Field(
        validation_alias="UnitName",
        description="Friendly name for machine",
        examples=["Vask 1", "Tumbler 1"],
    )
    symbol: int = Field(
        validation_alias="MachineSymbol",
        ge=0,
        le=7,
        repr=False,
        description="User interface symbol to signify the kind of machine, hardcoded meaning for all supported machine types. see kind property",
    )
    color: int = Field(
        validation_alias="MachineColor",
        ge=0,
        le=3,
        repr=False,
        description="User interface color to signify the status of a machine, hardcoded meaning for all supported colors. see status property",
    )
    text1: str = Field(validation_alias="Text1", examples=["Idle", "Time Left"])
    text2: str = Field(validation_alias="Text2", examples=["", "28 mins", "70 mins"])
    type: str = Field(validation_alias="MachineType", examples=["58", "59"])

    @computed_field
    @property
    def status(self) -> MachineStatus:
        return MachineStatus(self.color)

    @computed_field
    @property
    def kind(self) -> MachineKind:
        return MachineKind(self.symbol)

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return (self.laundry_number, self.group_number, self.number) < (
                other.laundry_number,
                other.group_number,
                other.number,
            )
        return NotImplemented


class LaundryStatesResponseDTO(BaseModel):
    """Response from /laundrystates endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK")
    result_text: str = Field(
        validation_alias="ResultText", examples=["", "Push"]
    )  # infrequently is set to "Push", behaviour erratic.

    machine_states: list[MachineStateDTO] = Field(validation_alias="MachineStates")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class VersionResponseDTO(BaseModel):
    """Response from /Version endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK")
    result_text: Optional[str] = Field(validation_alias="ResultText", examples=[""])

    major: int = Field(validation_alias="Major")
    minor: int = Field(validation_alias="Minor")
    build: int = Field(validation_alias="Build")
    revision: int = Field(validation_alias="Revision")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class TransactionDTO(BaseModel):
    laundry_number: int = Field(
        validation_alias="SerialNumber"
    )  # sent as str, treat as int.
    laundry_address: str = Field(
        validation_alias="LaundryAddress", examples=["H.C. Andersens Boulevard 34"]
    )
    machine_number: int = Field(validation_alias="MachineNumber", ge=0)
    program: int = Field(
        validation_alias="Program",
        ge=0,
        examples=[2, 5, 6, 8],
        description="the used program of the machine, follows top-bottom left-right of the machine interface",
    )
    temperature: int = Field(
        validation_alias="Temperature", ge=0, examples=[0, 30, 40, 60, 90]
    )
    transaction_time: dt.datetime = Field(validation_alias="TransactionTime")
    amount: int = Field(
        validation_alias="Amount",
        le=0,
        examples=[-1000],
        description="the cost of the transaction, given in 0.01 of 'currency' (øre) format",
    )
    balance: int = Field(
        validation_alias="Balance",
        examples=[0, -1000, -2000, -3000],
        description="the new balance after this transaction was completed, given in 0.01 of 'currency' (øre) format",
    )


class TransactionResponseDTO(BaseModel):
    """Response from /transactions endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK")
    result_text: str = Field(validation_alias="ResultText", examples=[""])

    transactions: list[TransactionDTO] = Field(validation_alias="Transactions")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self
