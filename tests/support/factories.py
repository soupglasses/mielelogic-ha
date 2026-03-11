from typing import Optional

from polyfactory import Use
from polyfactory.decorators import post_generated
from polyfactory.factories.pydantic_factory import ModelFactory

from mielelogic_api.dto import (
    LaundrySettingsDTO,
    CardDTO,
    LaundryDTO,
    DetailsResponseDTO,
    MachineStateDTO,
    LaundryStatesResponseDTO,
    VersionResponseDTO,
    TransactionDTO,
    TransactionResponseDTO,
)


class LaundrySettingsDTOFactory(ModelFactory[LaundrySettingsDTO]):
    __use_examples__ = True
    __by_name__ = True


class CardDTOFactory(ModelFactory[CardDTO]):
    __use_examples__ = True
    __by_name__ = True


class LaundryDTOFactory(ModelFactory[LaundryDTO]):
    __use_examples__ = True
    __by_name__ = True


class DetailsResponseDTOFactory(ModelFactory[DetailsResponseDTO]):
    __use_examples__ = True
    __by_name__ = True
    cards = Use(CardDTOFactory.batch, size=1)

    @post_generated
    @classmethod
    def accessible_laundries(
        cls,
        laundry_numbers: Optional[list[int]] = None,
        size: Optional[int] = None,
    ):
        size = cls.__random__.randint(1, 5) if size is None else size
        laundry_numbers = (
            [cls.__random__.randint(1000, 9999) for _ in range(size)]
            if laundry_numbers is None
            else laundry_numbers
        )

        return [
            LaundryDTOFactory.build(laundry_number=laundry_number)
            for laundry_number in laundry_numbers
        ]


class MachineStateDTOFactory(ModelFactory[MachineStateDTO]):
    __use_examples__ = True
    __by_name__ = True

    @post_generated
    @classmethod
    def text1(
        cls,
        text1: Optional[str] = None,
    ):
        if text1 is not None:
            return text1
        return ModelFactory.__random__.choice(["Idle", "Time left", "Reserved"])

    @post_generated
    @classmethod
    def text2(
        cls,
        text2: Optional[str] = None,
        text1: Optional[str] = None,
    ):
        if text2 is not None:
            return text2
        match text1:
            case "Idle":
                return " "
            case "Time left":
                return f"{ModelFactory.__random__.randint(1, 120)} min"
            case "Reserved":
                return (
                    f"{ModelFactory.__random__.randint(0, 23)}:"
                    f"{ModelFactory.__random__.randint(0, 59):02d}"
                )
            case _:
                return ""

    @post_generated
    @classmethod
    def machine_number(cls, machine_number: Optional[int] = None):
        return (
            ModelFactory.__random__.randint(1, 99)
            if machine_number is None
            else machine_number
        )


class LaundryStatesResponseDTOFactory(ModelFactory[LaundryStatesResponseDTO]):
    __use_examples__ = True
    __by_name__ = True

    @post_generated
    @classmethod
    def machine_states(
        cls,
        laundry_number: Optional[int] = None,
        machine_numbers: Optional[list[int]] = None,
        size: Optional[int] = None,
    ):
        size = cls.__random__.randint(1, 5) if size is None else size
        laundry_number = (
            cls.__random__.randint(1000, 9999)
            if laundry_number is None
            else laundry_number
        )
        machine_numbers = (
            [i + 1 for i in range(size)] if machine_numbers is None else machine_numbers
        )

        return [
            MachineStateDTOFactory.build(
                laundry_number=laundry_number,
                machine_number=machine_numbers[i],
            )
            for i in range(len(machine_numbers))
        ]


class VersionResponseDTOFactory(ModelFactory[VersionResponseDTO]):
    __use_examples__ = True
    __by_name__ = True


class TransactionDTOFactory(ModelFactory[TransactionDTO]):
    __use_examples__ = True
    __by_name__ = True

    @post_generated
    @classmethod
    def machine_number(cls, machine_number: Optional[int] = None):
        return (
            ModelFactory.__random__.randint(1, 99)
            if machine_number is None
            else machine_number
        )


class TransactionResponseDTOFactory(ModelFactory[TransactionResponseDTO]):
    __use_examples__ = True
    __by_name__ = True

    @post_generated
    @classmethod
    def transactions(
        cls,
        laundry_numbers: Optional[list[int]] = None,
        machine_numbers: Optional[list[int]] = None,
        size: Optional[int] = None,
    ) -> list[TransactionDTO]:
        size = cls.__random__.randint(1, 5) if size is None else size
        laundry_numbers = (
            [cls.__random__.randint(1000, 9999) for _ in range(size)]
            if laundry_numbers is None
            else laundry_numbers
        )
        machine_numbers = (
            [i + 1 for i in range(size)] if machine_numbers is None else machine_numbers
        )

        return [
            TransactionDTOFactory.build(
                laundry_number=ModelFactory.__random__.choice(laundry_numbers),
                machine_number=ModelFactory.__random__.choice(machine_numbers),
            )
            for _ in range(size)
        ]
