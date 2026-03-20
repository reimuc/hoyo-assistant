# HoyoAssistant

Your personal HoYoLAB automation assistant. Supports daily community tasks, game sign-in (CN/OS), cloud games (CN/OS), and optional push notifications.

![Build Status](https://img.shields.io/github/actions/workflow/status/reimuc/hoyo-assistant/build.yml?label=Build)
![Test Status](https://img.shields.io/github/actions/workflow/status/reimuc/hoyo-assistant/test_run.yml?label=Test)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- Automated sign-in for CN/OS game accounts
- Community tasks (read/like/share/check-in)
- Cloud game daily tasks (CN/OS support)
- Multi-account batch execution
- Optional push notification integrations
- Async runtime (`asyncio`, shared async HTTP client)

## Install

```powershell
pip install -e .
```

## Run Modes

### 1) Direct CLI Run (parameter/env-driven)

Use this mode for one-off runs, CI jobs, and cloud runners.

```powershell
# single (default)
hoyo-cli

# single with explicit config
hoyo-cli --config config\config.yaml

# multi (scan default config dir)
hoyo-cli --multi

# multi with explicit config list
hoyo-cli --multi --config config\a.yaml config\b.yaml
```

Priority notes (direct CLI run):

- Push executes only when `HOYO_ASSISTANT_PUSH__ENABLE=true` or `push=true` in YAML
- `--push-config` overrides default `config/push.ini` lookup

### 2) Server Scheduler Mode (interactive, isolated)

`server` is an independent scheduler entrypoint. It does not require run arguments.

- Startup reads local config discovery/defaults
- Runtime control is done inside the interactive console
- Command-line run flags/env overrides are intended for direct CLI run mode, not scheduler startup control

```powershell
hoyo-cli server
```

Server console commands:

- `run`: execute immediately
- `reload`: reload local config
- `mode <single|multi>`: switch runtime mode
- `interval <minutes>`: change scheduler interval (minimum 1 minute)
- `status`: show runtime status, next run, interval, mode
- `exit`: stop scheduler
- `help`: print command help

## Utility Commands

```powershell
# validate config file
hoyo-cli check -c config\config.yaml

# print effective runtime config (redacted)
hoyo-cli check -c config\config.yaml --effective

# generate template config
hoyo-cli template -o config\config.yaml

# auto-fill missing fields in an existing config file
hoyo-cli format -c config\config.yaml
```

## Environment Variables

Use `HOYO_ASSISTANT_` prefix with `__` for nesting.

Example:

- `games.cn.genshin.checkin` -> `HOYO_ASSISTANT_GAMES__CN__GENSHIN__CHECKIN=true`

Canonical source of truth:

- The list is intentionally concise for quick setup and CI use
- For fine-grained behavior, prefer YAML config files (`config/*.yaml`)

Common runtime keys:

- `HOYO_ASSISTANT_MODE`
- `HOYO_ASSISTANT_PUSH__ENABLE`
- `HOYO_ASSISTANT_CLI_OUTPUT`
- `HOYO_ASSISTANT_SYSTEM__LOG_LEVEL` (default: `INFO`)
- `HOYO_ASSISTANT_LOG_DIR` (default: `logs`)
- `HOYO_ASSISTANT_LOG_ROTATION` (default: `10 MB`)
- `HOYO_ASSISTANT_LOG_RETENTION` (default: `1 week`)
- `HOYO_ASSISTANT_LOG_CONSOLE_ENABLE` (default: `true`)
- `HOYO_ASSISTANT_LOG_FILE_ENABLE` (default: `true`)
- `HOYO_ASSISTANT_LANGUAGE` (default: `auto`)

Log level sources:

- `--debug` forces DEBUG for current run
- `HOYO_ASSISTANT_SYSTEM__LOG_LEVEL` controls default logger level

## Development

```powershell
pip install -e ".[dev]"
pytest
ruff check .
ruff format .
mypy
```

## Entrypoints

- Package CLI: `hoyo-cli` -> `src/hoyo_assistant/cli.py:main`
