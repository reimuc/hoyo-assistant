"""CN server cloud game sign-in tasks."""

import functools

from ...core import config, log, setting, t
from ...core.constants import (
    API_CLOUD_GENSHIN,
    API_CLOUD_GENSHIN_SIGN,
    API_CLOUD_ZZZ,
    API_CLOUD_ZZZ_SIGN,
)
from ...core.models import CloudGameInfo
from ..base import BaseCloudGame

CLOUD_GAMES = [
    CloudGameInfo("genshin", API_CLOUD_GENSHIN_SIGN, "hk4e_cn", API_CLOUD_GENSHIN),
    CloudGameInfo("zzz", API_CLOUD_ZZZ_SIGN, "nap_cn", API_CLOUD_ZZZ),
]


async def clear_cookie(code: str) -> None:
    if "cloud_games" in config and "cn" in config["cloud_games"]:
        config["cloud_games"]["cn"].setdefault(code, {})["token"] = ""
        await setting.save_config()


def _build_headers(token: str, game_biz: str, hostname: str | None) -> dict[str, str]:
    """Build headers for CN cloud game API."""
    headers: dict[str, str] = {
        "Accept": "*/*",
        "Referer": "https://app.mihoyo.com",
        "x-rpc-combo_token": token,
        "x-rpc-cg_game_biz": game_biz,
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
    }
    if hostname:
        headers["Host"] = hostname
    return headers


async def run_task() -> str:
    conf = config["cloud_games"]["cn"]
    log.info(t("games.cloud.start"))
    ret_msg = ""
    for game in CLOUD_GAMES:
        token = conf.get(game.name, {}).get("token")
        if conf.get(game.name, {}).get("enable") and token != "":
            headers = _build_headers(token, game.biz, game.hostname)
            game_task = BaseCloudGame(
                game=t(f"games.names.{game.name}"),
                url=game.api,
                coin_name=t(f"games.cloud.{game.name}_coin"),
                clear_cookie_func=functools.partial(clear_cookie, game.name),
                headers=headers,
            )
            ret_msg += await game_task.check_in(retry_on_limit=True) + "\n\n"

    return ret_msg
