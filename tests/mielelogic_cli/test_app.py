from __future__ import annotations

import datetime as dt
from argparse import Namespace

import pytest
from rich.columns import Columns
from rich.console import Group

from mielelogic_cli import app
from mielelogic_cli.app import DashboardSnapshot, KeyboardController, render_dashboard
from tests.support.factories import (
    DetailsResponseDTOFactory,
    LaundryDTOFactory,
    MachineStateDTOFactory,
)


def build_snapshot() -> DashboardSnapshot:
    first_laundry = LaundryDTOFactory.build(laundry_number=200, name="Second")
    second_laundry = LaundryDTOFactory.build(laundry_number=100, name="First")
    details = DetailsResponseDTOFactory.build(
        accessible_laundries=[first_laundry, second_laundry]
    )
    first_machine = MachineStateDTOFactory.build(
        laundry_number=200,
        machine_number=9,
        unit_name="Machine Nine",
    )
    second_machine = MachineStateDTOFactory.build(
        laundry_number=200,
        machine_number=1,
        unit_name="Machine One",
    )
    return DashboardSnapshot(
        fetched_at=dt.datetime.now(),
        details=details,
        machine_states={
            200: [first_machine, second_machine],
            100: [],
        },
    )


def test_render_dashboard_preserves_api_order():
    layout = render_dashboard(build_snapshot(), refresh_remaining_seconds=30)

    laundry_group = layout["body"].renderable
    assert isinstance(laundry_group, Group)

    first_panel = laundry_group.renderables[0]
    second_panel = laundry_group.renderables[1]
    assert first_panel.title == "Second (200)"
    assert second_panel.title == "First (100)"

    first_columns = first_panel.renderable
    assert isinstance(first_columns, Columns)
    machine_titles = [panel.title for panel in first_columns.renderables]
    assert machine_titles == ["Machine Nine #9", "Machine One #1"]


@pytest.mark.parametrize("key", ["q", "\x1b", "\x03"])
def test_keyboard_controller_quit_keys(key: str):
    controller = KeyboardController()

    controller.handle_key(key)

    assert controller.quit_requested is True


def test_keyboard_controller_debounces_manual_refresh():
    controller = KeyboardController(debounce_seconds=5)

    controller.handle_key("r", now=10.0)
    assert controller._refresh_event.is_set() is True
    controller._refresh_event.clear()

    controller.handle_key("r", now=12.0)
    assert controller._refresh_event.is_set() is False

    controller.handle_key("r", now=15.1)
    assert controller._refresh_event.is_set() is True


def test_main_swallows_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app, "parse_args", lambda: Namespace(refresh_seconds=60))

    def raise_keyboard_interrupt(coro: object) -> None:
        coro.close()
        raise KeyboardInterrupt

    monkeypatch.setattr(app.asyncio, "run", raise_keyboard_interrupt)

    app.main()
