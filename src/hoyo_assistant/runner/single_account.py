import asyncio
import os
import random
import re

from ..core import config, login, push, tools
from ..core.constants import StatusCode
from ..core.error import CookieError, StokenError
from ..core.i18n import t
from ..core.loghelper import log
from ..tasks.cn import cloud_games, game_signin
from ..tasks.community import miyoushe
from ..tasks.os import cloud_games as os_cloud_games, game_signin as os_game_signin
from ..tasks.web import activities as web_activities


def _normalize_output_text(text: str) -> str:
    """Normalize output text for console/push/log readability."""
    if not text:
        return ""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


async def initialize_config(
    config_path: str | None = None, use_env: bool = True
) -> tuple[bool, str | None]:
    # Force reload if config_path provided (multi-account must load each file separately).
    # For single-account, reload only on first run if no config_path was ever loaded.
    if config_path:
        # Multi-account: always reload the specified file
        config.load_config(config_path, use_env=use_env)
    elif not config.config_path:
        # Single-account first run: load default or discover config
        config.load_config(None, use_env=use_env)

    if not config.config.get("enable"):
        log.warning(t("config.not_enabled"))
        return False, t("config.not_enabled")
    return True, None


async def handle_login() -> None:
    account_cfg = config.config["account"]
    if any(
        (
            account_cfg["stuid"] == "",
            account_cfg["stoken"] == "",
            account_cfg["mid"] == "",
        )
    ):
        if config.config["mihoyobbs"]["enable"]:
            await login.login()
            await asyncio.sleep(random.randint(3, 8))
        account_cfg["cookie"] = tools.tidy_cookie(account_cfg["cookie"])


async def run_miyoushe_tasks() -> tuple[str, bool]:
    """
    Run Miyoushe community tasks.
    Returns:
        tuple[str, bool]: (result_message, is_stoken_error)
    """
    return_data = ""
    raise_stoken = False

    if not config.config["mihoyobbs"]["enable"]:
        return return_data, raise_stoken

    if config.config["account"]["stoken"] == "StokenError":
        return t("mihoyobbs.stoken_error"), True

    try:
        bbs = miyoushe.Mihoyobbs()
        task_result = await bbs.run_task()
        return_data += task_result
    except StokenError:
        return_data = t("mihoyobbs.stoken_error")
        raise_stoken = True
    except Exception as e:
        return_data = t("mihoyobbs.task_error", error=e)
        log.error(t("mihoyobbs.task_error", error=e))

    return return_data, raise_stoken


async def run_cn_signin_tasks() -> str:
    result = []
    if config.config["games"]["cn"]["enable"]:
        # Direct call to module run_task
        result.append(await game_signin.run_task())
    if config.config["cloud_games"]["cn"]["enable"]:
        # Direct call to module run_task
        result.append(await cloud_games.run_task())
    return "\n\n".join(filter(None, result))


async def run_os_signin_tasks() -> str:
    result = []
    if config.config["games"]["os"]["enable"]:
        os_result = await os_game_signin.run_task()
        if os_result:
            result.append(f"{t('games.os.title')}{os_result}")

    if config.config["cloud_games"]["os"]["enable"]:
        result.append(await os_cloud_games.run_task())

    return "\n\n".join(filter(None, result))


async def run_web_activity_tasks() -> None:
    # await run_web_activity_bundle()
    if config.config["web_activity"]["enable"]:
        log.info(t("web_activity.start_msg"))
        await web_activities.run_task()


async def run_once(
    config_path: str | None = None, use_env: bool = True
) -> tuple[int, str]:
    success, msg = await initialize_config(config_path, use_env=use_env)
    if not success:
        return StatusCode.FAILURE.value, msg or ""

    # Clear HTTP cache right after config reload to ensure fresh API calls with new credentials
    from ..core.request import http

    http.cache.clear()
    http.clear_cookies()
    log.debug("HTTP cache cleared after config load")

    await handle_login()

    if config.config["account"]["cookie"] == "CookieError":
        raise CookieError(t("account.cookie_invalid"))

    return_data = []
    status_code = StatusCode.SUCCESS.value

    miyoushe_result, raise_stoken = await run_miyoushe_tasks()
    return_data.append(miyoushe_result)
    return_data.append(await run_cn_signin_tasks())
    return_data.append(await run_os_signin_tasks())

    await run_web_activity_tasks()

    if raise_stoken:
        raise StokenError(t("account.stoken_error"))

    normalized_parts = [_normalize_output_text(x) for x in return_data if x]
    normalized_parts = [x for x in normalized_parts if x]
    result_msg = "\n\n".join(normalized_parts)
    if not result_msg:
        result_msg = t("cli.task.no_result")

    if t("games.cn.captcha_trigger") in result_msg or "验证码" in result_msg:
        status_code = StatusCode.CAPTCHA_TRIGGERED.value

    return status_code, result_msg


def _is_push_enabled() -> bool:
    env_enable = str(os.getenv("HOYO_ASSISTANT_PUSH__ENABLE", "")).strip().lower()
    if env_enable in {"true", "1", "on", "yes"}:
        return True
    push_flag = str(config.config.get("push", "")).strip().lower()
    return push_flag in {"true", "1", "on", "yes"}


async def run_once_and_push(
    config_path: str | None = None,
    push_config_path: str | None = None,
    use_env: bool = True,
) -> tuple[int, str]:
    # Keep compatibility with test/mocked callables that only accept positional config_path.
    if use_env:
        run_code, run_msg = await run_once(config_path)
    else:
        run_code, run_msg = await run_once(config_path, use_env=use_env)
    if not _is_push_enabled():
        return run_code, run_msg

    if push_config_path:
        await push.push(run_code, run_msg, config_path=push_config_path)
    else:
        await push.push(run_code, run_msg)

    return run_code, run_msg
