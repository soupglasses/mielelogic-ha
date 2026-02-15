# MieleLogic Home Assistant Integration

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [poe](https://poethepoet.natn.io/) for task running.

### Quick Start

```bash
# Install dependencies and set up pre-commit hooks
uv sync
poe setup

# Run tests
poe test

# Other useful commands
poe console   # Interactive Python shell with project loaded
poe lint      # Check code style
poe format    # Auto-format code
poe build     # Build distribution packages
```

### Requirements

- uv (install via `pip install uv` or see [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/))

## Legal Disclaimer

*This project is an independent, unofficial integration and is not endorsed by, affiliated with, or sponsored by Miele & Cie. KG, its subsidiaries, or MieleLogic. All product names, logos, brands, trademarks, and registered trademarks are property of their respective owners.*

**Usage is at your own risk!**

### Trademark Notice

*Miele® and MieleLogic® are registered trademarks of their respective owners. This project's use of these names is for identification and reference purposes only and does not imply any endorsement or affiliation.*
