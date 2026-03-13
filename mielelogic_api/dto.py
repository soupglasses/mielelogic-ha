import datetime as dt
import logging
import re
from enum import Enum
from functools import total_ordering
from typing import Any, Optional, Self

from pydantic import AliasChoices, BaseModel, Field, computed_field, model_validator

_LOGGER = logging.getLogger(__name__)


class ApiDTO(BaseModel):
    """Base model for DTOs that can be serialized back to API wire format."""

    def to_api(self) -> dict[str, Any]:
        """Return the DTO in API response/request shape without computed fields."""
        return {
            self._api_field_name(name): self._api_serialize(getattr(self, name))
            for name in self.__class__.model_fields
        }

    @classmethod
    def _api_field_name(cls, field_name: str) -> str:
        field = cls.model_fields[field_name]
        if field.serialization_alias is not None:
            return field.serialization_alias
        if isinstance(field.validation_alias, str):
            return field.validation_alias
        if isinstance(field.validation_alias, AliasChoices):
            first_choice = field.validation_alias.choices[0]
            if isinstance(first_choice, str):
                return first_choice
        return field_name

    @classmethod
    def _api_serialize(cls, value: Any) -> Any:
        if isinstance(value, ApiDTO):
            return value.to_api()
        if isinstance(value, list):
            return [cls._api_serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._api_serialize(item) for key, item in value.items()}
        if isinstance(value, dt.datetime):
            return value.isoformat()
        return value


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


class MachineTextStatus(str, Enum):
    """Status derived from text1/text2 fields — more granular than MachineStatus color.

    The API sends text1/text2 pairs that carry richer state information than the
    color field alone:

    - Idle:     text1="Idle",      text2=" "        — machine is free
    - Running:  text1="Time left", text2="28 min"   — running with countdown
    - Reserved: text1="Reserved until",  text2="20:08"    — reserved, shows end time
    - Unknown:  anything else while machine_color is non-idle
    """

    Idle = "idle"
    Running = "timed_run"
    Reserved = "reserved"
    Unknown = "unknown"


class LaundrySettingsDTO(ApiDTO):
    """Laundry settings from /Details endpoint."""

    phone_number: str = Field(validation_alias="PhoneNumber", examples=["12345678"])
    laundry_language: str = Field(validation_alias="LaundryLanguage", examples=["da"])
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


class CardDTO(ApiDTO):
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
        validation_alias="AccountBallance",  # API-side typo "Ballance"
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
class LaundryDTO(ApiDTO):
    """Laundry facility information from /Details endpoint."""

    laundry_number: int = Field(
        validation_alias="LaundryNumber", ge=0, le=9999
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
            return self.laundry_number < other.laundry_number
        return NotImplemented


class DetailsResponseDTO(ApiDTO):
    """Response from /Details endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
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
class MachineStateDTO(ApiDTO):
    """Machine state information from /laundrystates endpoint."""

    laundry_number: int = Field(validation_alias="LaundryNumber", ge=0, le=9999)
    group_number: int = Field(
        validation_alias="GroupNumber",
        ge=0,
        description="Grouping of machines, may be used to signify different rooms or different kinds of machines",
        examples=[0, 1],
    )
    machine_number: int = Field(validation_alias="MachineNumber", ge=0)
    unit_name: str = Field(
        validation_alias="UnitName",
        description="Friendly name for machine",
        examples=["Vask 1", "Tumbler 1"],
    )
    machine_symbol: int = Field(
        validation_alias="MachineSymbol",
        ge=0,
        le=7,
        repr=False,
        description="User interface symbol to signify the kind of machine, hardcoded meaning for all supported machine types. see kind property",
    )
    machine_color: int = Field(
        validation_alias="MachineColor",
        ge=0,
        le=3,
        repr=False,
        description="User interface color to signify the status of a machine, hardcoded meaning for all supported colors. see status property",
    )
    text1: str = Field(
        validation_alias="Text1",
        examples=["Idle", "Time left", "Reserved until"],
    )
    text2: str = Field(
        validation_alias="Text2",
        examples=[" ", "28 min", "70 min", "20:08"],
    )
    machine_type: str = Field(validation_alias="MachineType", examples=["58", "59"])

    @computed_field
    @property
    def machine_status(self) -> MachineStatus:
        return MachineStatus(self.machine_color)

    @computed_field
    @property
    def machine_kind(self) -> MachineKind:
        return MachineKind(self.machine_symbol)

    @computed_field
    @property
    def machine_text_status(self) -> MachineTextStatus:
        """Derive a fine-grained status from text1.

        Falls back to Idle when machine_color is Idle regardless of text1,
        and to Unknown for unrecognised text1 on a non-idle machine.
        """
        if self.machine_status == MachineStatus.Idle:
            return MachineTextStatus.Idle
        if self.text1 == "Time left":
            return MachineTextStatus.Running
        if self.text1 == "Reserved until":
            return MachineTextStatus.Reserved
        return MachineTextStatus.Unknown

    @computed_field
    @property
    def minutes_remaining(self) -> int | None:
        """Minutes remaining parsed from text2 when text1 is 'Time left'.

        Looks for the first integer in text2 (e.g. "28 min" → 28).
        Returns None for all other states.
        """
        if self.machine_text_status != MachineTextStatus.Running:
            return None
        match = re.search(r"\d+", self.text2)
        if match:
            return int(match.group())
        _LOGGER.warning(
            "machine %s: could not parse minutes from text2=%r",
            self.unit_name,
            self.text2,
        )
        return None

    @computed_field
    @property
    def reserved_until(self) -> dt.time | None:
        """Reservation end time parsed from text2 when text1 is 'Reserved'.

        Looks for an HH:MM pattern in text2 (e.g. "20:08").
        Warns and returns None if the pattern is absent or the value is not a valid time.
        """
        if self.machine_text_status != MachineTextStatus.Reserved:
            return None
        # TODO: validate if 7:00 or 07:00 is correct.
        match = re.search(r"(\d{1,2}):(\d{2})", self.text2)
        if match:
            try:
                return dt.time(int(match.group(1)), int(match.group(2)))
            except ValueError:
                pass
        _LOGGER.warning(
            "machine %s: could not parse HH:MM time from text2=%r",
            self.unit_name,
            self.text2,
        )
        return None

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return (self.laundry_number, self.group_number, self.machine_number) < (
                other.laundry_number,
                other.group_number,
                other.machine_number,
            )
        return NotImplemented


class LaundryStatesResponseDTO(ApiDTO):
    """Response from /laundrystates endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
    result_text: str = Field(
        validation_alias="ResultText", examples=[""]
    )  # If set to "Push", do not trust this payload and refetch after 1 second.

    machine_states: list[MachineStateDTO] = Field(validation_alias="MachineStates")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class VersionResponseDTO(ApiDTO):
    """Response from /Version endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
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


class TimeSlotStatus(str, Enum):
    """Status of a timetable slot."""

    Reserved = "Reserved"
    Available = "Available"


class ReservationDTO(ApiDTO):
    """A single reservation entry from /reservations endpoint."""

    laundry_number: int = Field(
        validation_alias="LaundryNumber", ge=0, le=9999, examples=[1234]
    )
    machine_number: int = Field(validation_alias="MachineNumber", ge=0, examples=[1])
    machine_name: str = Field(validation_alias="MachineName", examples=["Machine 1"])
    specialuser: int = Field(validation_alias="Specialuser", examples=[0])
    start: dt.datetime = Field(
        validation_alias="Start", examples=["2025-01-01T10:00:00"]
    )
    end: dt.datetime = Field(validation_alias="End", examples=["2025-01-01T11:30:00"])


class ReservationsResponseDTO(ApiDTO):
    """Response from GET /reservations endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
    result_text: str = Field(validation_alias="ResultText", examples=[""])

    max_user_reservations: int = Field(
        validation_alias="MaxUserReservations", ge=0, examples=[2]
    )
    reservations: list[ReservationDTO] = Field(validation_alias="Reservations")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class ReservationReceiptResponseDTO(ApiDTO):
    """Response from GET /reservations/receipt endpoint.

    Used for polling after create/delete: ResultText transitions
    from "InQueue" to "Created". Both states have ResultOK=true.
    """

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
    result_text: str = Field(validation_alias="ResultText", examples=["Created"])

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class TimeSlotDTO(ApiDTO):
    """A single timetable slot."""

    start: dt.datetime = Field(
        validation_alias="Start", examples=["2025-01-01T10:00:00"]
    )
    end: dt.datetime = Field(validation_alias="End", examples=["2025-01-01T11:30:00"])
    status: TimeSlotStatus = Field(validation_alias="Status", examples=["Available"])


class MachineTimeTableDTO(ApiDTO):
    """A machine's timetable from /timetable endpoint."""

    machine_number: int = Field(validation_alias="MachineNumber", ge=0, examples=[1])
    machine_name: str = Field(validation_alias="MachineName", examples=["Machine 1"])
    period_start: dt.datetime = Field(
        validation_alias="PeriodStart", examples=["2025-01-01T10:00:00"]
    )
    period_end: dt.datetime = Field(
        validation_alias="PeriodEnd", examples=["2025-02-01T10:00:00"]
    )
    time_table: list[TimeSlotDTO] = Field(validation_alias="TimeTable")


class TimetableResponseDTO(ApiDTO):
    """Response from GET /country/{scope}/laundry/{id}/timetable endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
    result_text: str = Field(validation_alias="ResultText", examples=["OK"])

    laundry_number: int = Field(
        validation_alias="LaundryNumber", ge=0, le=9999, examples=[1234]
    )
    laundry_name: str = Field(
        validation_alias="LaundryName", examples=["Example Laundry"]
    )
    max_user_reservations: int = Field(
        validation_alias="MaxUserReservations", ge=0, examples=[2]
    )
    machine_time_tables: dict[str, MachineTimeTableDTO] = Field(
        validation_alias="MachineTimeTables"
    )

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self


class TransactionDTO(ApiDTO):
    laundry_number: int = Field(
        validation_alias="SerialNumber", ge=0, le=9999
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


class TransactionResponseDTO(ApiDTO):
    """Response from /transactions endpoint."""

    result_ok: bool = Field(validation_alias="ResultOK", examples=[True])
    result_text: str = Field(validation_alias="ResultText", examples=[""])

    transactions: list[TransactionDTO] = Field(validation_alias="Transactions")

    @model_validator(mode="after")
    def validate_result_ok(self) -> Self:
        if not self.result_ok:
            raise ValueError(
                f"Invalid {self.__class__.__name__}: {self.result_text!r}."
            )
        return self
