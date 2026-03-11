# AGENTS.md

## Project summary

This repository contains two related but separate Python code areas in one uv project:

1. `mielelogic_api/` The standalone async MieleLogic API client library.
2. `custom_components/mielelogic/` The Home Assistant custom integration that uses the client library.

Keep these concerns separated in code structure, even though the development environment is shared.

## Environment usage

- For agent execution, prefer `uv run ...` for Python-related commands instead of shell activation.
- Do not write `uv run ...` in user-facing documentation or examples unless the task explicitly asks for it.
- User-facing documentation should assume an activated environment via `source .venv/bin/activate` or `source .envrc`, then show commands without the `uv run` prefix.
- Use `uv sync` only when dependencies or dependency groups changed, or when the environment is inconsistent.
- Do not add extra wrapper env vars or command flags unless there is a concrete reason.

## `uv sync`

- Use `uv sync` when dependencies or dependency groups changed, or when the environment is inconsistent with `pyproject.toml` / `uv.lock`.
- Run it from the repo root.
- Do not use `uv sync` casually before every command.

## Poe usage

- For agent execution, prefer Poe through `uv run`.
- In user-facing docs, assume the environment is already activated and show plain `poe ...` commands.

- `poe test` is for the library and CLI tests only. It runs as `pytest tests/mielelogic_cli tests/mielelogic_api` in the shared `.venv`.
- `poe test-ha` is for Home Assistant integration tests only. It runs as `pytest tests/custom_components/mielelogic` in the shared `.venv`.
- `poe test-network` is for the opt-in live API tests marked with `@pytest.mark.network`.

## Verification

- After changing code, run the relevant test suite, possibly limiting to tests touching the changes you have made, before considering the work done.
- For root library changes, run:

```bash
poe test  # pytest tests/mielelogic_cli tests/mielelogic_api
```

- For Home Assistant integration changes, run:

```bash
poe test-ha  # pytest tests/custom_components/mielelogic
```

- For changes that affect both layers, run:

```bash
poe test-all  # sequence running `poe test` then `poe test-ha`
```

- Run lint, then tests, then format. Do not run tests a second time if the format changes anything. We trust that ruff does not change behaviour.

## Root vs HA test separation

- The root library code and the Home Assistant integration remain separate code areas.
- The shared `.venv` includes both the root dev tools and the HA test stack.
- Keep the test entrypoints separate: `poe test` for `tests/mielelogic_cli` and `tests/mielelogic_api`, `poe test-ha` for `tests/custom_components/mielelogic`.

## Networked tests

- Tests marked with `@pytest.mark.network` are real live API checks and should remain marked.
- Do not remove the marker.
- It is acceptable for these tests to be skipped, it only validates that the external API still acts as we encode into the DTO objects and factories.
- If live verification is needed, ask the user to run the command outside the sandbox.

## Ruff / formatting

Linting and formatting are minor cleanup steps. Run them once at the end, during verification, after the relevant tests pass and you are done applying changes.

- Prefer Poe wrappers:

```bash
poe lint  # ruff check .
poe lint-fix  # ruff check --fix .
poe format  # ruff format .
```

- Do not run lint or format repeatedly while still implementing changes unless there is a concrete need.

## What not to do

- Do not use `PYTEST_DISABLE_PLUGIN_AUTOLOAD`.
- Do not change DTO definitions or factory logic. These need to stay EXACTLY equivalent to the live API. This is important.
- Do not remove or replace the existing `pydantic_settings` `.env` handling for unless the user explicitly asks for that exact change.
- Do not change `poe` commands unless asked to do so.
