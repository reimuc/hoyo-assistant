import asyncio
import os
import sys
import threading
import time
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel

from .core import config, log, push, setting, t
from .core.models import ServerSettings
from .runner import run_multi_account, run_single_account

console = Console()


def start_interactive_console(cfg: ServerSettings | None = None) -> None:
    """
    Start the interactive server console.
    """
    if cfg is None:
        cfg = ServerSettings()
    # help static type-checkers: after this point cfg is definitely a ServerSettings
    assert cfg is not None

    cfg.running = True
    console.clear()
    console.print(
        Panel(
            f"[bold green]{t('cli.task.server_console_title')}[/bold green]",
            border_style="green",
        )
    )

    # Print welcome message and next run time
    console.print(f"[cyan]{t('cli.task.server_console_started', mode=cfg.mode)}[/cyan]")
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
    cfg.next_run = time.time() + cfg.interval
    next_dt = datetime.fromtimestamp(cfg.next_run)
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
        while cfg.running:
            try:
                cmd = (
                    console.input("[bold cyan]hoyo-server>[/bold cyan] ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                console.print(f"\n[yellow]{t('cli.task.server_stopping')}[/yellow]")
                cfg.running = False
                cfg.stop_event.set()
                break

            if cmd in ["exit", "quit", "stop"]:
                console.print(f"[yellow]{t('cli.task.server_stopping')}[/yellow]")
                cfg.running = False
                cfg.stop_event.set()
                break
            elif cmd in ["help", "?"]:
                print_help()
            elif cmd == "run":
                console.print(f"[green]{t('cli.task.server_force_run')}[/green]")
                # We force run by setting next_run to NOW (or past)
                # But scheduler loop sleeps for 1 sec.
                # So setting it to 0 ensures it runs on next tick.
                cfg.next_run = 0
            elif cmd == "reload":
                console.print(f"[green]{t('cli.task.server_reloading')}[/green]")
                setting.reload_config(use_env=cfg.use_env)
            elif cmd.startswith("mode "):
                parts = cmd.split()
                if len(parts) > 1 and parts[1] in ["single", "multi"]:
                    cfg.mode = parts[1]
                    console.print(
                        f"[green]{t('cli.task.server_mode_set', mode=cfg.mode)}[/green]"
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
                    datetime.fromtimestamp(cfg.next_run)
                    if cfg.next_run > 0
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
                if cfg.last_run > 0:
                    last_run_str = datetime.fromtimestamp(cfg.last_run).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                console.print(
                    Panel(
                        t(
                            "cli.task.server_status_body",
                            mode=cfg.mode,
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
        cfg.running = False
        cfg.stop_event.set()
        scheduler_thread.join(timeout=5)
        sys.exit(0)


def print_help() -> None:
    console.print(
        Panel(
            t("cli.task.server_help_body"),
            title=t("cli.task.server_help_title"),
        )
    )


def scheduler_loop(cfg: ServerSettings) -> None:
    """
    Main scheduler loop running in separate thread.
    """
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log.info(
        t("cli.task.server_scheduler_started", interval=cfg.interval, mode=cfg.mode)
    )

    # Next run is already scheduled by the main thread or default
    if cfg.next_run == 0:
        cfg.next_run = time.time()

    while cfg.running and not cfg.stop_event.is_set():
        now = time.time()
        if now >= cfg.next_run:
            log.info(t("cli.task.server_scheduler_running", mode=cfg.mode))
            cfg.last_run = now

            # Execute task
            try:
                loop.run_until_complete(execute_task(cfg))
            except Exception as e:
                log.error(
                    t("cli.task.server_exec_error", mode="execution", error=str(e))
                )

            # Schedule next run
            cfg.next_run = time.time() + cfg.interval
            next_dt = datetime.fromtimestamp(cfg.next_run)
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


async def execute_task(cfg: ServerSettings) -> None:
    """
    Execute the task logic based on mode.
    """
    start_time = time.time()
    current_mode = cfg.mode

    try:
        if current_mode == "single":
            cfg_path = cfg.config_path
            if isinstance(cfg_path, list):
                target_path = cfg_path[0] if cfg_path else None
            else:
                target_path = cfg_path
            status_code, msg = await run_single_account(
                config_path=target_path,
                push_config_path=cfg.push_config_path,
                use_env=cfg.use_env,
            )
        else:
            status_code, msg = await run_multi_account(
                target_path=cfg.config_path,
                push_config_path=cfg.push_config_path,
                use_env=cfg.use_env,
            )
    except Exception as e:
        status_code = 1
        msg = t("cli.task.server_exec_error", mode=current_mode, error=str(e))
        log.error(msg)

    elapsed = time.time() - start_time
    log.info(t("cli.task.server_task_done", time=elapsed, status=status_code))

    env_enable = str(os.getenv("HOYO_ASSISTANT_PUSH__ENABLE", "")).strip().lower()
    cfg_push = config.get("push", "")
    cfg_enable = str(cfg_push).strip().lower() in {"true", "1", "on", "yes"}
    push_enabled = env_enable in {"true", "1", "on", "yes"} or cfg_enable

    if push_enabled:
        # Push summary
        try:
            await push.push(status_code, msg, config_path=cfg.push_config_path)
        except Exception as e:
            log.error(t("cli.task.server_push_fail", error=e))
