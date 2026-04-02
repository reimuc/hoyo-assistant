import asyncio
import os
import random
from collections.abc import Iterable

from ..core import config, push
from ..core.constants import StatusCode
from ..core.error import CookieError, StokenError
from ..core.i18n import t
from ..core.loghelper import log
from .single_account import run_once


def _normalize_targets(target_path: str | list[str] | None) -> list[str]:
    if target_path is None:
        return []
    if isinstance(target_path, list):
        return [str(p).strip() for p in target_path if str(p).strip()]
    return [p.strip() for p in str(target_path).split(",") if p.strip()]


def _collect_config_pool(paths: Iterable[str]) -> list[tuple[str, str]]:
    pool: list[tuple[str, str]] = []
    seen: set[str] = set()  # Track absolute paths to avoid duplicates

    for single_path in paths:
        if os.path.isfile(single_path):
            abs_path = os.path.abspath(single_path)
            if abs_path not in seen:
                seen.add(abs_path)
                pool.append((os.path.dirname(abs_path), os.path.basename(abs_path)))
        elif os.path.isdir(single_path):
            for f in os.listdir(single_path):
                if f.endswith((".yaml", ".yml")):
                    abs_path = os.path.abspath(os.path.join(single_path, f))
                    if abs_path not in seen:
                        seen.add(abs_path)
                        pool.append((single_path, f))
        else:
            log.warning(t("multi.path_not_exists", path=single_path))
    return pool


def _is_push_enabled() -> bool:
    env_enable = str(os.getenv("HOYO_ASSISTANT_PUSH__ENABLE", "")).strip().lower()
    if env_enable in {"true", "1", "on", "yes"}:
        return True
    push_flag = str(config.config.get("push", "")).strip().lower()
    return push_flag in {"true", "1", "on", "yes"}


async def run_multi_account(
    target_path: str | list[str] | None = None,
    push_config_path: str | None = None,
    use_env: bool = True,
) -> tuple[int, str]:
    """Execute tasks for multiple config files sequentially. Each run_once() is isolated:
    config reload, cache clear, and no env precedence ensure account independence."""
    log.info(t("multi.title"))
    log.info(t("multi.searching_config"))

    # Collect config files
    config_pool = []
    target_paths = _normalize_targets(target_path)
    if target_paths:
        config_pool.extend(_collect_config_pool(target_paths))
    else:
        # Default: search config/ dir
        search_path = (
            config.path
            if config.path and os.path.isdir(config.path)
            else os.path.join(os.getcwd(), "config")
        )
        if os.path.exists(search_path):
            for f in os.listdir(search_path):
                if f.endswith((".yaml", ".yml")):
                    config_pool.append((search_path, f))

    if not config_pool:
        log.warning(t("multi.no_config_found"))
        return StatusCode.FAILURE.value, t("multi.no_config_found")

    log.info(t("multi.config_found", count=len(config_pool)))

    results: dict[str, list[str]] = {"ok": [], "close": [], "error": [], "captcha": []}

    for dir_path, file_name in config_pool:
        log.info(t("multi.executing", file=file_name))
        full_path = str(os.path.join(dir_path, file_name))

        try:
            # Call run_once with explicit config file; it handles reload and execution isolation.
            run_code, _ = await run_once(full_path, use_env=use_env)
        except (CookieError, StokenError) as e:
            results["error"].append(file_name)
            error_msg = (
                t("multi.cookie_error")
                if isinstance(e, CookieError)
                else t("multi.stoken_error")
            )
            if _is_push_enabled():
                if push_config_path:
                    await push.push(
                        StatusCode.FAILURE.value,
                        error_msg,
                        config_path=push_config_path,
                    )
                else:
                    await push.push(StatusCode.FAILURE.value, error_msg)
        else:
            if run_code == StatusCode.SUCCESS.value:
                results["ok"].append(file_name)
            elif run_code in (
                StatusCode.FAILURE.value,
                StatusCode.PARTIAL_FAILURE.value,
            ):
                results["error"].append(file_name)
            elif run_code == StatusCode.CAPTCHA_TRIGGERED.value:
                results["captcha"].append(file_name)
            else:
                results["close"].append(file_name)

        log.info(t("multi.exec_done", file=file_name))
        await asyncio.sleep(random.randint(3, 10))

    push_message = t(
        "multi.summary",
        total=len(config_pool),
        ok=len(results["ok"]),
        close=len(results["close"]),
        error=len(results["error"]),
        captcha=len(results["captcha"]),
        close_list=results["close"],
        error_list=results["error"],
        captcha_list=results["captcha"],
    )
    log.debug(push_message)

    status = StatusCode.SUCCESS.value
    if len(results["error"]) == len(config_pool):
        status = StatusCode.FAILURE.value
    elif len(results["error"]) != 0:
        status = StatusCode.PARTIAL_FAILURE.value
    elif len(results["captcha"]) != 0:
        status = StatusCode.CAPTCHA_TRIGGERED.value

    return status, push_message
