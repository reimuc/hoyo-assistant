import asyncio
import os
import sys
import threading
import time
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel

from .core import config, push
from .core.i18n import t
from .core.loghelper import log
from .runner.multi_account import run_multi_account
from .runner.single_account import run_once

console = Console()


class ServerConfig:
    def __init__(
        self,
        mode: str = "multi",
        config_path: str | list[str] | None = None,
        push_config_path: str | None = None,
    ):
        self._interval_seconds: int = 720 * 60  # 12 hours
        self._mode: str = mode  # "single" or "multi"
        # config_path may be a single path or a list in other contexts; keep runtime flexible
        self._config_path: str | list[str] | None = (
            config_path  # For run_once or run_multi_account
        )
        self._push_config_path: str | None = push_config_path
        self._last_run: float = 0.0
        self._next_run: float = 0.0
        self._running: bool = False
        self._stop_event: threading.Event = threading.Event()
        # Server mode uses local config/defaults only and ignores env runtime overrides.
        self._use_env = False

    @property
    def interval(self) -> int:
        return self._interval_seconds

    @interval.setter
    def interval(self, seconds: int) -> None:
        self._interval_seconds = max(60, seconds)


def start_interactive_console(cfg: ServerConfig | None = None) -> None:
    """
    Start the interactive server console.
    """
    if cfg is None:
        cfg = ServerConfig()

    cfg._running = True
    console.clear()
    console.print(
        Panel(
            f"[bold green]{t('cli.task.server_console_title')}[/bold green]",
            border_style="green",
        )
    )

    # Print welcome message and next run time
    console.print(
        f"[cyan]{t('cli.task.server_console_started', mode=cfg._mode)}[/cyan]"
    )
    console.print(f"[cyan]{t('cli.task.server_next_run_immediate')}[/cyan]")

    # Run the first task synchronously in the main thread to ensure logs don't clash with the prompt
    try:
        asyncio.run(execute_task(cfg))
    except Exception as e:
        log.error(
            t("cli.task.server_exec_error", mode="initial_execution", error=str(e))
        )

    # Wait a bit for pending logs to flush (Rich console might buffer)
    time.sleep(0.2)

    # Schedule the next run
    cfg._next_run = time.time() + cfg.interval
    next_dt = datetime.fromtimestamp(cfg._next_run)
    console.print(
        f"[dim]{t('cli.task.server_scheduler_next', next_run=next_dt.strftime('%Y-%m-%d %H:%M:%S'))}[/dim]"
    )

    # Start scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, args=(cfg,), daemon=True)
    scheduler_thread.start()

    # Sleep a short while to allow the scheduler thread to output its start message
    # before we print the prompt. This avoids the race condition visually.
    time.sleep(0.1)

    try:
        while cfg._running:
            try:
                cmd = (
                    console.input("[bold cyan]hoyo-server>[/bold cyan] ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                console.print(f"\n[yellow]{t('cli.task.server_stopping')}[/yellow]")
                cfg._running = False
                cfg._stop_event.set()
                break

            if cmd in ["exit", "quit", "stop"]:
                console.print(f"[yellow]{t('cli.task.server_stopping')}[/yellow]")
                cfg._running = False
                cfg._stop_event.set()
                break
            elif cmd in ["help", "?"]:
                print_help()
            elif cmd == "run":
                console.print(f"[green]{t('cli.task.server_force_run')}[/green]")
                # We force run by setting next_run to NOW (or past)
                # But scheduler loop sleeps for 1 sec.
                # So setting it to 0 ensures it runs on next tick.
                cfg._next_run = 0
            elif cmd == "reload":
                console.print(f"[green]{t('cli.task.server_reloading')}[/green]")
                config.reload_config(use_env=cfg._use_env)
            elif cmd.startswith("mode "):
                parts = cmd.split()
                if len(parts) > 1 and parts[1] in ["single", "multi"]:
                    cfg._mode = parts[1]
                    console.print(
                        f"[green]{t('cli.task.server_mode_set', mode=cfg._mode)}[/green]"
                    )
                else:
                    console.print(f"[red]{t('cli.task.server_invalid_mode')}[/red]")
            elif cmd.startswith("interval "):
                parts = cmd.split()
                if len(parts) > 1 and parts[1].isdigit():
                    minutes = int(parts[1])
                    cfg.interval = minutes * 60
                    console.print(
                        f"[green]{t('cli.task.server_interval_set', minutes=cfg.interval // 60, seconds=cfg.interval)}[/green]"
                    )
                else:
                    console.print(f"[red]{t('cli.task.server_invalid_interval')}[/red]")
            elif cmd == "status":
                next_run_dt = (
                    datetime.fromtimestamp(cfg._next_run)
                    if cfg._next_run > 0
                    else datetime.now()
                )
                # time_left can be a timedelta when computed, or a string when rendered
                time_left: timedelta | str = next_run_dt - datetime.now()
                if isinstance(time_left, timedelta) and time_left.total_seconds() < 0:
                    time_left = t("cli.task.server_status_running")
                else:
                    # If it's timedelta, format; if already a string, keep it
                    if isinstance(time_left, timedelta):
                        time_left = str(time_left).split(".")[0]

                last_run_str = t("cli.task.server_last_run_never")
                if cfg._last_run > 0:
                    last_run_str = datetime.fromtimestamp(cfg._last_run).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                console.print(
                    Panel(
                        t(
                            "cli.task.server_status_body",
                            mode=cfg._mode,
                            interval=cfg.interval,
                            last_run=last_run_str,
                            next_run=next_run_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            time_left=time_left,
                        ),
                        title=t("cli.task.server_status_title"),
                    )
                )
            elif cmd == "":
                pass
            else:
                console.print(
                    f"[red]{t('cli.task.server_unknown_command', cmd=cmd)}[/red]"
                )

    except Exception as e:
        log.error(t("cli.task.server_exec_error", mode="console", error=str(e)))
    finally:
        cfg._running = False
        cfg._stop_event.set()
        scheduler_thread.join(timeout=5)
        sys.exit(0)


def print_help() -> None:
    console.print(
        Panel(
            t("cli.task.server_help_body"),
            title=t("cli.task.server_help_title"),
        )
    )


def scheduler_loop(cfg: ServerConfig) -> None:
    """
    Main scheduler loop running in separate thread.
    """
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log.info(
        t("cli.task.server_scheduler_started", interval=cfg.interval, mode=cfg._mode)
    )

    # Next run is already scheduled by the main thread or default
    if cfg._next_run == 0:
        cfg._next_run = time.time()

    while cfg._running and not cfg._stop_event.is_set():
        now = time.time()
        if now >= cfg._next_run:
            log.info(t("cli.task.server_scheduler_running", mode=cfg._mode))
            cfg._last_run = now

            # Execute task
            try:
                loop.run_until_complete(execute_task(cfg))
            except Exception as e:
                log.error(
                    t("cli.task.server_exec_error", mode="execution", error=str(e))
                )

            # Schedule next run
            cfg._next_run = time.time() + cfg.interval
            next_dt = datetime.fromtimestamp(cfg._next_run)
            log.info(
                t(
                    "cli.task.server_scheduler_next",
                    next_run=next_dt.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )

        # Sleep a bit to avoid CPU spin
        time.sleep(1)

    loop.close()
    log.info(t("cli.task.server_scheduler_stopped"))


async def execute_task(cfg: ServerConfig) -> None:
    """
    Execute the task logic based on mode.
    """
    start_time = time.time()

    status_code = 0
    msg = ""

    current_mode = cfg._mode

    try:
        if current_mode == "single":
            # run_once expects an Optional[str]; guard against list[str] being passed from config
            cfg_path = cfg._config_path if isinstance(cfg._config_path, str) else None
            status_code, msg = await run_once(cfg_path, use_env=cfg._use_env)
        else:
            status_code, msg = await run_multi_account(
                target_path=cfg._config_path,
                push_config_path=cfg._push_config_path,
                use_env=cfg._use_env,
            )
    except Exception as e:
        status_code = 1
        msg = t("cli.task.server_exec_error", mode=current_mode, error=str(e))
        log.error(msg)

    elapsed = time.time() - start_time
    log.info(t("cli.task.server_task_done", time=elapsed, status=status_code))

    env_enable = str(os.getenv("HOYO_ASSISTANT_PUSH__ENABLE", "")).strip().lower()
    # Use config.config safely with None check
    cfg_push = config.config.get("push", "") if config.config else ""
    cfg_enable = str(cfg_push).strip().lower() in {"true", "1", "on", "yes"}
    push_enabled = env_enable in {"true", "1", "on", "yes"} or cfg_enable

    if push_enabled:
        # Push summary
        try:
            await push.push(status_code, msg, config_path=cfg._push_config_path)
        except Exception as e:
            log.error(t("cli.task.server_push_fail", error=e))
