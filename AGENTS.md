# AGENTS Guide

## Purpose and Entry

- This repo automates HoYoLAB/MiYoUShe daily tasks plus optional push notifications.
- Main entrypoint is `hoyo-cli` -> `src/hoyo_assistant/cli.py:main` (`pyproject.toml`).
- Direct run mode defaults to single account; add `--multi` for multi-account.

## Build and CI/CD

- **Build**: Use `.github/workflows/build.yml` to generate artifacts.
    - Triggers on push/dispatch.
    - Builds Wheel and Sdist packages.
    - Compiles standalone executable using PyInstaller (`dist/hoyo-assistant`).
- **Test & Run**: Use `.github/workflows/test_run.yml` for execution.
    - Triggers on push/schedule/dispatch.
    - Uses `scripts/smoke_test.py` for integration validation.

## Runtime Envorinment Variables (Non-Pydantic)

These variables control system behavior outside the main configuration schema:

- **Logging**:
    - `HOYO_ASSISTANT_LOG_DIR` (default: `logs`): Log output directory.
    - `HOYO_ASSISTANT_LOG_ROTATION` (default: `10 MB`): Log rotation size.
    - `HOYO_ASSISTANT_LOG_RETENTION` (default: `1 week`): Log retention period.
    - `HOYO_ASSISTANT_LOG_CONSOLE_ENABLE` (default: `true`): Toggle console logging.
    - `HOYO_ASSISTANT_LOG_FILE_ENABLE` (default: `true`): Toggle file logging.
    - `HOYO_ASSISTANT_SYSTEM__LOG_LEVEL` (default: `INFO`): Global log level.

- **Interface**:
    - `HOYO_ASSISTANT_CLI_OUTPUT`: Output mode (`rich`, `plain`, `auto`).
    - `HOYO_ASSISTANT_LANGUAGE`: Force UI language (`zh_CN`, `en_US`).
    - `LANG`: System language fallback.

- **Validation**:
    - `HOYO_ASSISTANT_PUSH__ENABLE` (default: `false`): Global master switch for push notifications.

## Architecture Quick Map

- `src/hoyo_assistant/cli.py`: arg parsing, run-mode resolution, config bootstrap/reload, runner dispatch.
- `src/hoyo_assistant/core/config.py` + `core/config_schema.py`: file/env merge, runtime overrides, schema validation.
- `src/hoyo_assistant/runner/single_account.py`: one-account orchestration + optional push.
- `src/hoyo_assistant/runner/multi_account.py`: config target discovery, per-account loop, summary aggregation.
- `src/hoyo_assistant/core/request.py`: shared async HTTP client (retry + GET cache).
- `src/hoyo_assistant/core/push.py`: `PushHandler` provider dispatch.
- `src/hoyo_assistant/tasks/**`: feature modules exposing `run_task()`.

- `src/hoyo_assistant/core/request.py`: shared async HTTP client (retry + GET cache). Exports a global
  `http` client instance used across modules; supports TTL caching (GET), MockResponse for cache hits,
  and tenacity-based retries.
- `src/hoyo_assistant/server.py`: interactive scheduler / server console (implements `ServerConfig`,
  `start_interactive_console`, `scheduler_loop` and `execute_task`). Used by the `server` CLI subcommand
  to run scheduled multi/single account runs with an interactive prompt.
