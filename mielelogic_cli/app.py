"""Rich-based dashboard for viewing current machine state."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys
import termios
import time
import tty
from contextlib import AbstractContextManager
from dataclasses import dataclass

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from pydantic import SecretStr

from mielelogic_api import MieleLogicAuthError, MieleLogicClient, MieleLogicError
from mielelogic_api.dto import DetailsResponseDTO, LaundryDTO, MachineStateDTO
from mielelogic_api.settings import MieleLogicCredentials, load_environment_credentials

_STATUS_COLORS = {
    "Closed": "grey50",
    "Idle": "green",
    "Busy": "red",
    "Disabled": "grey50",
}

_MANUAL_REFRESH_DEBOUNCE_SECONDS = 5
_QUIT_KEYS = {"q", "\x1b", "\x03"}
_CONNECTING_ERROR = RuntimeError("Connecting...")


@dataclass(slots=True)
class DashboardSnapshot:
    """Current live data shown in the CLI dashboard."""

    fetched_at: dt.datetime
    details: DetailsResponseDTO
    machine_states: dict[int, list[MachineStateDTO]]


@dataclass(slots=True)
class DashboardView:
    """Current render state for the live dashboard."""

    snapshot: DashboardSnapshot | None = None
    error: Exception | None = None

    @classmethod
    def connecting(cls) -> DashboardView:
        """Create the initial loading state."""
        return cls(error=_CONNECTING_ERROR)

    def render(self, *, refresh_remaining_seconds: int) -> Layout:
        if self.snapshot is not None:
            return render_dashboard(
                self.snapshot,
                refresh_remaining_seconds=refresh_remaining_seconds,
            )
        if self.error is not None:
            return render_error(
                self.error,
                refresh_remaining_seconds=refresh_remaining_seconds,
            )
        return render_error(
            _CONNECTING_ERROR,
            refresh_remaining_seconds=refresh_remaining_seconds,
        )


class KeyboardController(AbstractContextManager["KeyboardController"]):
    """Handle single-key shortcuts for the live dashboard."""

    def __init__(self, *, debounce_seconds: int = _MANUAL_REFRESH_DEBOUNCE_SECONDS):
        self._debounce_seconds = debounce_seconds
        self._refresh_event = asyncio.Event()
        self._quit_requested = False
        self._last_manual_refresh_at = 0.0
        self._fd: int | None = None
        self._original_termios: list | None = None
        self._reader_installed = False

    @property
    def quit_requested(self) -> bool:
        return self._quit_requested

    def __enter__(self) -> KeyboardController:
        if not sys.stdin.isatty():
            return self
        self._fd = sys.stdin.fileno()
        self._original_termios = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        asyncio.get_running_loop().add_reader(self._fd, self._read_key)
        self._reader_installed = True
        return self

    def __exit__(self, *_) -> None:
        if self._fd is not None and self._reader_installed:
            asyncio.get_running_loop().remove_reader(self._fd)
        if self._fd is not None and self._original_termios is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_termios)
        self._reader_installed = False
        self._fd = None
        self._original_termios = None

    def handle_key(self, key: str, *, now: float | None = None) -> None:
        """Process a keyboard shortcut."""
        if key.lower() in _QUIT_KEYS:
            self._quit_requested = True
            self._refresh_event.set()
            return
        if key.lower() == "r":
            current = time.monotonic() if now is None else now
            if current - self._last_manual_refresh_at >= self._debounce_seconds:
                self._last_manual_refresh_at = current
                self._refresh_event.set()

    async def wait_for_refresh(self, timeout: float) -> bool:
        """Wait for either a manual or timed refresh trigger."""
        try:
            await asyncio.wait_for(self._refresh_event.wait(), timeout=timeout)
        except TimeoutError:
            return False
        self._refresh_event.clear()
        return True

    def _read_key(self) -> None:
        if self._fd is None:
            return
        key = os.read(self._fd, 1).decode(errors="ignore")
        if key:
            self.handle_key(key)


def _build_header(snapshot: DashboardSnapshot) -> RenderableType:
    card = snapshot.details.cards[0] if snapshot.details.cards else None
    balance = f"{card.account_balance:.2f} {card.currency}" if card else "n/a"
    summary = Table.grid(expand=True)
    summary.add_column(justify="left")
    summary.add_column(justify="right")
    summary.add_row(
        f"[bold cyan]Scope[/] {card.card_laundry_number if card else snapshot.details.apartment_number}",
        f"[bold magenta]Balance[/] {balance}",
    )
    summary.add_row(
        f"[bold cyan]Apartment[/] {snapshot.details.apartment_number}",
        f"[bold white]Updated[/] {snapshot.fetched_at.strftime('%H:%M:%S')}",
    )
    return Panel(summary, title="MieleLogic CLI", border_style="cyan")


def _machine_panel(machine: MachineStateDTO) -> Panel:
    status = machine.machine_status.name
    kind = machine.machine_kind.name
    color = _STATUS_COLORS[status]
    body = Table.grid(padding=(0, 1))
    body.add_column()
    body.add_column()
    body.add_row("kind", kind)
    body.add_row("status", f"[{color}]{status}[/]")
    body.add_row("line 1", machine.text1 or "-")
    body.add_row("line 2", machine.text2 or "-")
    return Panel(
        body,
        title=f"{machine.unit_name} #{machine.machine_number}",
        subtitle=f"group {machine.group_number}",
        border_style=color,
    )


def _laundry_panel(laundry: LaundryDTO, machines: list[MachineStateDTO]) -> Panel:
    cards = Columns(
        [_machine_panel(machine) for machine in machines],
        expand=True,
        equal=True,
    )
    title = f"{laundry.name} ({laundry.laundry_number})"
    subtitle = f"{laundry.address}, {laundry.zip_code}"
    return Panel(cards, title=title, subtitle=subtitle, border_style="blue")


def _empty_panel(message: str, *, style: str = "yellow") -> Panel:
    return Panel(Align.center(message, vertical="middle"), border_style=style)


def _footer_panel(refresh_remaining_seconds: int) -> Panel:
    label = (
        f"refreshing in {refresh_remaining_seconds}s"
        if refresh_remaining_seconds > 0
        else "refreshing now"
    )
    return Panel(
        f"[dim]q / esc / ctrl+c quit • r refresh now (5s debounce) • {label}[/dim]",
        border_style="grey50",
    )


def render_dashboard(
    snapshot: DashboardSnapshot, *, refresh_remaining_seconds: int
) -> Layout:
    """Build the Rich layout for the current snapshot."""
    layout = Layout()
    layout.split_column(
        Layout(_build_header(snapshot), size=6),
        Layout(name="body"),
        Layout(_footer_panel(refresh_remaining_seconds), size=3),
    )

    laundry_panels = [
        _laundry_panel(laundry, snapshot.machine_states.get(laundry.laundry_number, []))
        for laundry in snapshot.details.accessible_laundries
    ]
    if not laundry_panels:
        layout["body"].update(
            _empty_panel("No accessible laundries reported by the API.")
        )
    else:
        layout["body"].update(Group(*laundry_panels))
    return layout


def render_error(error: Exception, *, refresh_remaining_seconds: int) -> Layout:
    """Render a full-screen error layout."""
    layout = Layout()
    layout.split_column(
        Layout(
            _empty_panel(f"Unable to load machine state.\n\n{error}", style="red"),
            name="body",
        ),
        Layout(_footer_panel(refresh_remaining_seconds), size=3),
    )
    return layout


def prompt_for_credentials(console: Console) -> MieleLogicCredentials:
    """Show a login page in the terminal and collect credentials."""
    login_table = Table.grid(padding=(0, 1))
    login_table.add_row("[bold cyan]Username[/]", "Your MieleLogic account username")
    login_table.add_row("[bold cyan]Password[/]", "Your MieleLogic account password")
    login_table.add_row("[bold cyan]Scope[/]", "Country scope, DA or NO")
    console.clear()
    console.print(
        Panel(
            Align.center(login_table),
            title="Login",
            subtitle="Environment credentials not found",
            border_style="cyan",
        )
    )
    username = SecretStr(Prompt.ask("Username"))
    password = SecretStr(Prompt.ask("Password", password=True))
    scope = Prompt.ask("Scope", default="DA", choices=["DA", "NO"], show_choices=True)
    return MieleLogicCredentials(
        username=username,
        password=password,
        scope=scope,
    )


async def fetch_snapshot(client: MieleLogicClient) -> DashboardSnapshot:
    """Fetch all live data needed for the dashboard."""
    details = await client.details()
    machine_states: dict[int, list[MachineStateDTO]] = {}
    for laundry in details.accessible_laundries:
        states = await client.laundry_states(laundry.laundry_number)
        machine_states[laundry.laundry_number] = states.machine_states
    return DashboardSnapshot(
        fetched_at=dt.datetime.now(),
        details=details,
        machine_states=machine_states,
    )


async def _load_dashboard_view(client: MieleLogicClient) -> DashboardView:
    """Load the next dashboard state, falling back to an error view."""
    try:
        return DashboardView(snapshot=await fetch_snapshot(client))
    except MieleLogicError as error:
        return DashboardView(error=error)


async def _wait_for_next_refresh(
    *,
    keyboard: KeyboardController,
    live: Live,
    current_view: DashboardView,
    refresh_seconds: int,
) -> None:
    """Update the dashboard until a refresh or quit is requested."""
    for remaining in range(refresh_seconds, -1, -1):
        live.update(
            current_view.render(refresh_remaining_seconds=remaining),
            refresh=True,
        )
        if remaining == 0 or keyboard.quit_requested:
            return
        if await keyboard.wait_for_refresh(timeout=1):
            return


async def run_dashboard(
    credentials: MieleLogicCredentials,
    *,
    refresh_seconds: int,
    console: Console,
) -> None:
    """Run the live Rich dashboard until interrupted."""
    async with MieleLogicClient(**credentials.as_client_kwargs()) as client:
        with (
            KeyboardController() as keyboard,
            Live(
                DashboardView.connecting().render(refresh_remaining_seconds=0),
                console=console,
                screen=True,
            ) as live,
        ):
            while not keyboard.quit_requested:
                current_view = await _load_dashboard_view(client)
                await _wait_for_next_refresh(
                    keyboard=keyboard,
                    live=live,
                    current_view=current_view,
                    refresh_seconds=refresh_seconds,
                )


async def run_app(refresh_seconds: int) -> None:
    """Resolve credentials, show login when needed, and start the dashboard."""
    console = Console()
    credentials = load_environment_credentials() or prompt_for_credentials(console)

    while True:
        try:
            await run_dashboard(
                credentials,
                refresh_seconds=refresh_seconds,
                console=console,
            )
            return
        except MieleLogicAuthError:
            console.print(
                Panel(
                    "Authentication failed. Please log in again.",
                    title="Auth Error",
                    border_style="red",
                )
            )
            credentials = prompt_for_credentials(console)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="MieleLogic machine dashboard")
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=60,
        help="Refresh interval for live machine state polling.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    try:
        asyncio.run(run_app(refresh_seconds=args.refresh_seconds))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
