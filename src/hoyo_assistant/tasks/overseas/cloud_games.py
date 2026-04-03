"""Overseas server cloud game sign-in tasks."""

import functools

from ...core import config, log, setting, t
from ...core.constants import API_CLOUD_GENSHIN_SIGN_OS, API_CLOUD_ZZZ_SIGN_OS
from ...core.models import CloudGameInfo
from ..base import BaseCloudGame

CLOUD_GAMES = [
    CloudGameInfo("genshin", API_CLOUD_GENSHIN_SIGN_OS, "hk4e_global"),
    CloudGameInfo("zzz", API_CLOUD_ZZZ_SIGN_OS, "nap_global"),
]


async def clear_cookie(code: str) -> None:
    if "cloud_games" in config and "os" in config["cloud_games"]:
        config["cloud_games"]["os"].setdefault(code, {})["token"] = ""
        await setting.save_config()


def _build_headers(token: str, game_biz: str, lang: str) -> dict[str, str]:
    """Build headers for OS cloud game API."""
    return {
        "Accept": "*/*",
        "x-rpc-combo_token": token,
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "okhttp/4.10.0",
        "x-rpc-client_type": "3",
        "x-rpc-cg_game_biz": game_biz,
        "x-rpc-channel_id": "1",
        "x-rpc-language": lang,
    }


async def run_task() -> str:
    conf = config["cloud_games"]["os"]
    log.info(t("games.cloud.start"))
    ret_msg = ""
    for game in CLOUD_GAMES:
        token = conf.get(game.name, {}).get("token")
        if conf.get(game.name, {}).get("enable") and token != "":
            lang = conf.get("lang", "zh-cn")
            headers = _build_headers(token, game.biz, lang)
            game_task = BaseCloudGame(
                game=t(f"games.names.{game.name}"),
                url=game.api,
                coin_name=t(f"games.cloud.{game.name}_coin"),
                clear_cookie_func=functools.partial(clear_cookie, game.name),
                headers=headers,
            )
            ret_msg += await game_task.check_in() + "\n\n"

    return ret_msg
