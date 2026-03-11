#!/usr/bin/env python3
"""Export the current live MieleLogic API state to a JSON snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from mielelogic_api import MieleLogicClient
from mielelogic_api.settings import load_environment_credentials


async def export_snapshot(output_path: Path) -> None:
    """Fetch the current live API state and write it to disk."""
    credentials = load_environment_credentials()
    if credentials is None:
        msg = "Missing MieleLogic credentials in environment."
        raise RuntimeError(msg)
    created_at = dt.datetime.now().astimezone()
    transactions_to = created_at.replace(minute=0, second=0, microsecond=0)
    transactions_from = transactions_to - dt.timedelta(hours=24)

    async with MieleLogicClient(
        **credentials.as_client_kwargs(),
    ) as client:
        version = await client.version()
        details = await client.details()
        transactions = await client.transactions(
            from_=transactions_from,
            to_=transactions_to,
        )
        laundry_states = {
            str(laundry.laundry_number): (
                await client.laundry_states(laundry.laundry_number)
            ).model_dump(mode="json")
            for laundry in details.accessible_laundries
        }

    snapshot = {
        "snapshot_created_at": created_at.isoformat(),
        "scope": credentials.scope,
        "version": version.model_dump(mode="json"),
        "details": details.model_dump(mode="json"),
        "transactions": {
            "date_from": transactions_from.isoformat(),
            "date_to": transactions_to.isoformat(),
            "response": transactions.model_dump(mode="json"),
        },
        "laundry_states": laundry_states,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    timestamp = dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    default_output = Path("snapshots") / f"mielelogic-live-{timestamp}.json"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_output,
        help="Output path for the snapshot JSON file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    import asyncio

    args = parse_args()
    asyncio.run(export_snapshot(args.output))
