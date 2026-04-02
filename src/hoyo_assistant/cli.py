import argparse
import asyncio
import json
import os
import sys
from contextlib import suppress
from typing import Any

from rich.console import Console
from rich.panel import Panel

from . import server
from .core import config
from .runner import multi_account, single_account


def _configure_stdio_encoding() -> None:
    """Prefer UTF-8 console output to avoid emoji encoding failures on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")


_configure_stdio_encoding()


def _is_interactive_terminal() -> bool:
    stdout = getattr(sys, "stdout", None)
    stderr = getattr(sys, "stderr", None)
    return bool(
        getattr(stdout, "isatty", lambda: False)()
        and getattr(stderr, "isatty", lambda: False)()
    )


def _use_rich_output() -> bool:
    mode = os.getenv("HOYO_ASSISTANT_CLI_OUTPUT", "auto").strip().lower()
    if mode in {"plain", "text", "simple", "0", "false", "off"}:
        return False
    if mode in {"rich", "pretty", "1", "true", "on"}:
        return True
    return _is_interactive_terminal()


RICH_OUTPUT = _use_rich_output()
console = Console(no_color=not RICH_OUTPUT, force_terminal=RICH_OUTPUT)


def cli_print(message: str, style: str | None = None) -> None:
    if style and RICH_OUTPUT:
        console.print(f"[{style}]{message}[/{style}]")
    else:
        console.print(message)


def cli_panel(
    message: str, title: str | None = None, border_style: str = "cyan"
) -> None:
    if RICH_OUTPUT:
        console.print(Panel(message, title=title, border_style=border_style))
    else:
        if title:
            console.print(f"[{title}]")
        console.print(message)


def print_banner() -> None:
    """Print the application banner."""
    from .core.i18n import t

    if not RICH_OUTPUT:
        return

    title = t("cli.banner.title")
    subtitle = t("cli.banner.subtitle")
    if RICH_OUTPUT:
        console.print(
            Panel.fit(
                f"[bold cyan]{title}[/bold cyan]\n[dim]{subtitle}[/dim]",
                border_style="cyan",
            )
        )


def _resolve_run_mode(args: Any) -> str:
    if getattr(args, "multi", False):
        return "multi"
    # Auto-detect multi mode if multiple configs provided
    configs = getattr(args, "configs", None)
    if isinstance(configs, list) and len(configs) > 1:
        return "multi"
    return "single"


def build_cli_overrides(
    args: Any, run_mode: str
) -> tuple[str | list[str] | None, dict[str, Any], str | None]:
    """Build runtime config overrides from CLI arguments without mutating process env."""
    overrides: dict[str, Any] = {}
    config_target: str | list[str] | None = None
    raw_push_config = getattr(args, "push_config", None)
    push_config_path: str | None = None

    # Normalize push_config_path to absolute path to avoid relative path resolution bugs
    if raw_push_config:
        push_config_path = str(
            os.path.abspath(os.path.expanduser(str(raw_push_config)))
        )

    # Global --config can be one or more paths.
    config_val = getattr(args, "configs", None)
    if config_val:
        if isinstance(config_val, list):
            cleaned = [str(item).strip() for item in config_val if str(item).strip()]
            if cleaned:
                if run_mode == "multi":
                    config_target = cleaned if len(cleaned) > 1 else cleaned[0]
                else:
                    config_target = cleaned[0]
        else:
            config_target = str(config_val)

    normalized_push_config: str | None = (
        str(push_config_path) if push_config_path is not None else None
    )
    return config_target, overrides, normalized_push_config


def _bootstrap_config_target(config_target: str | list[str] | None) -> str | None:
    """Return one file path for initial config bootstrap/reload."""
    if isinstance(config_target, list):
        return config_target[0] if config_target else None
    return config_target


async def run_single(push_config_path: str | None = None) -> None:
    """Execute single account task."""
    from .core.i18n import t

    cli_print(t("cli.task.single_start"), style="green")
    try:
        run_code, run_msg = await single_account.run_once_and_push(
            push_config_path=push_config_path
        )
        if run_msg:
            cli_panel(
                run_msg,
                title=t("cli.task.exec_report"),
                border_style="green" if run_code == 0 else "red",
            )
    except Exception as e:
        from .core.i18n import t

        cli_print(t("cli.task.single_fail", error=e), style="red")
        sys.exit(1)


async def run_multi_async(
    target_path: str | list[str] | None = None,
    push_config_path: str | None = None,
    use_env: bool = True,
) -> None:
    """Execute multi-account task async."""
    from .core.i18n import t

    cli_print(t("cli.task.multi_start"), style="green")
    task_status, task_push_message = await multi_account.run_multi_account(
        target_path, push_config_path=push_config_path, use_env=use_env
    )
    from .core.i18n import t

    cli_panel(
        task_push_message,
        title=t("cli.task.exec_report"),
        border_style="green" if task_status == 0 else "red",
    )


def run_multi_manager(args: Any, push_config_path: str | None = None) -> None:
    """Execution logic for multi account command"""

    target_path: str | list[str] | None = None
    # Multi-file execution should keep per-file account isolation and avoid env credential bleed-through.
    use_env = False

    # Priority is unified with single mode: explicit --config first, then env cookies.
    if hasattr(args, "configs") and args.configs:
        cfg = args.configs
        if isinstance(cfg, list):
            cleaned = [str(item).strip() for item in cfg if str(item).strip()]
            if cleaned:
                target_path = cleaned if len(cleaned) > 1 else cleaned[0]
        else:
            target_path = str(cfg)
    else:
        target_path = None

    asyncio.run(
        run_multi_async(target_path, push_config_path=push_config_path, use_env=use_env)
    )


def print_effective_config() -> None:
    """Print current effective config with redacted secrets."""
    from .core.config import get_effective_config
    from .core.i18n import t

    effective = get_effective_config(redact=True)
    payload = json.dumps(effective, ensure_ascii=False, indent=2)
    cli_panel(payload, title=t("cli.task.effective_config"), border_style="cyan")


def validate_config(config_path: str | None, show_effective: bool = False) -> None:
    """Validate the configuration file at config_path against the schema."""
    from .core.config import validate_config_file
    from .core.i18n import t

    if not config_path:
        config_path = config.config_path

    if not config_path or not os.path.exists(config_path):
        cli_print(t("cli.task.config_missing"), style="red")
        return

    cli_print(t("cli.task.validating", path=config_path), style="yellow")
    is_valid, errors = validate_config_file(config_path)

    if is_valid:
        cli_print(t("cli.task.valid"), style="green")
    else:
        cli_print(t("cli.task.invalid"), style="red")
        for error in errors:
            console.print(f"  - {error}")

    if show_effective:
        print_effective_config()


def generate_template(output_path: str | None) -> None:
    """Generate a default configuration template."""
    import yaml

    from .core.config import DEFAULT_CONFIG, save_config_sync
    from .core.i18n import t

    cli_print(t("cli.task.gen_template"), style="yellow")

    # Determine output path
    if output_path:
        output_path = str(os.path.expanduser(output_path))

    # Save the default config
    try:
        if output_path:
            save_config_sync(output_path, DEFAULT_CONFIG)
            cli_print(t("cli.task.template_saved", path=output_path), style="green")
        else:
            rendered = yaml.dump(
                DEFAULT_CONFIG,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
            sys.stdout.write(rendered)
            if not rendered.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
            cli_print(t("cli.task.template_saved", path="stdout"), style="green")
    except Exception as e:
        cli_print(t("cli.task.template_save_fail", error=e), style="red")


def fill_config_command(config_path: str, create_backup: bool = True) -> None:
    """Auto-fill and format a config file."""
    from .core.config import auto_fill_config_file
    from .core.i18n import t

    if not config_path:
        cli_print(t("cli.task.config_missing"), style="red")
        return

    config_path = str(os.path.expanduser(config_path))

    cli_print(t("cli.task.validating", path=config_path), style="cyan")
    success, message = auto_fill_config_file(config_path, backup=create_backup)

    if success:
        cli_print(message, style="green")
    else:
        cli_print(message, style="red")
        sys.exit(1)


def main() -> None:
    print_banner()
    from .core.i18n import t

    parser = argparse.ArgumentParser(
        description=t("cli.parser.description"),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Global args
    parser.add_argument(
        "-c", "--config", dest="configs", nargs="+", help=t("cli.parser.config")
    )
    parser.add_argument("-p", "--push-config", help=t("cli.parser.push_config"))
    parser.add_argument(
        "-m", "--multi", action="store_true", help=t("cli.parser.multi")
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help=t("cli.parser.debug")
    )

    subparsers = parser.add_subparsers(dest="command", help=t("cli.parser.commands"))

    # Server command
    subparsers.add_parser("server", help=t("cli.parser.server"))

    # Check command
    check_parser = subparsers.add_parser("check", help=t("cli.parser.check"))
    check_parser.add_argument("-c", "--config", help=t("cli.parser.check_config"))
    check_parser.add_argument(
        "--effective",
        action="store_true",
        help=t("cli.parser.check_effective"),
    )

    # Template command
    template_parser = subparsers.add_parser("template", help=t("cli.parser.template"))
    template_parser.add_argument("-o", "--output", help=t("cli.parser.template_output"))

    # Fill config command
    fill_config_parser = subparsers.add_parser("format", help=t("cli.parser.format"))
    fill_config_parser.add_argument(
        "-c", "--config", required=True, help=t("cli.parser.format_config")
    )
    fill_config_parser.add_argument(
        "--no-backup", action="store_true", help=t("cli.parser.format_no_backup")
    )

    args = parser.parse_args()

    is_server_command = args.command == "server"

    if is_server_command:
        # Server mode is an independent scheduler entrypoint.
        # It always uses default local config discovery and interactive mode switch.
        run_mode = "multi"
        # Provide explicit type annotations so mypy does not complain about implicitly Optional variables
        config_target: str | list[str] | None
        cli_overrides: dict[str, Any]
        push_config_path: str | None
        config_target, cli_overrides, push_config_path = None, {}, None
    else:
        run_mode = _resolve_run_mode(args)
        config_target, cli_overrides, push_config_path = build_cli_overrides(
            args, run_mode
        )

    # Reload config with runtime overrides (CLI > env > YAML).
    # Server mode intentionally ignores CLI/env runtime overrides for scheduler isolation.
    try:
        if is_server_command:
            config.reload_config(config_file=None, overrides={}, use_env=False)
        else:
            # Bootstrap must be a single file path even when runtime target is a list.
            config.reload_config(
                config_file=_bootstrap_config_target(config_target),
                overrides=cli_overrides,
            )
    except ValueError as e:
        cli_print(t("cli.task.config_error", error=e), style="red")
        sys.exit(1)

    if args.debug:
        from .core.loghelper import setup_logger

        setup_logger("DEBUG")

    if args.command == "check":
        validate_config(args.config, getattr(args, "effective", False))
    elif args.command == "template":
        generate_template(args.output)
    elif args.command == "format":
        fill_config_command(args.config, not args.no_backup)
    elif args.command == "server":
        try:
            # Check if server starts successfully
            from .core.i18n import t  # Need to import locally or move to file level

            cli_print(t("cli.task.server_start"), style="green")
            if hasattr(server, "start_interactive_console"):
                cfg = server.ServerConfig()
                server.start_interactive_console(cfg)
            else:
                cli_print(t("cli.task.server_no_console"), style="red")
        except Exception as e:
            from .core.i18n import t

            cli_print(t("cli.task.server_fail", error=e), style="red")
    else:
        if run_mode == "multi":
            run_multi_manager(args, push_config_path=push_config_path)
        else:
            if len(sys.argv) == 1:
                cli_print(t("cli.help.no_args"), style="yellow")
            asyncio.run(run_single(push_config_path=push_config_path))


if __name__ == "__main__":
    main()
