import asyncio
import functools
import random
from collections.abc import Callable
from typing import Any

from ...core import config, tools
from ...core.constants import (
    API_CLOUD_GENSHIN,
    API_CLOUD_GENSHIN_SIGN,
    API_CLOUD_ZZZ,
    API_CLOUD_ZZZ_SIGN,
)
from ...core.i18n import t
from ...core.loghelper import log
from ...core.models import CloudGameInfo
from ...core.request import http

CLOUD_GAMES = [
    CloudGameInfo("genshin", API_CLOUD_GENSHIN_SIGN, "hk4e_cn", API_CLOUD_GENSHIN),
    CloudGameInfo("zzz", API_CLOUD_ZZZ_SIGN, "nap_cn", API_CLOUD_ZZZ),
]


async def clear_cookie(code: str) -> None:
    if "cloud_games" in config.config and "cn" in config.config["cloud_games"]:
        config.config["cloud_games"]["cn"].setdefault(code, {})["token"] = ""
        await config.save_config()


class CloudGame:
    def __init__(
        self,
        game: str,
        url: str,
        token: str,
        hostname: str | None,
        game_biz: str,
        coin_name: str,
        clear_cookie_func: Callable[[], Any],
    ) -> None:
        self.game = game
        self.url = url
        self.coin_name = coin_name
        self.clear_cookie_func = clear_cookie_func
        self.headers = {
            "Host": hostname,
            "Accept": "*/*",
            "Referer": "https://app.mihoyo.com",
            "x-rpc-combo_token": token,
            "x-rpc-cg_game_biz": game_biz,
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
        }

    async def check_in(self) -> str:
        log.info(t("games.cloud.checkin_start", game=self.game))
        ret_msg = ""

        try:
            res = await http.get(url=self.url, headers=self.headers)
            print(res.text())
            data = await res.json()

            if data["retcode"] == 0:
                free_time = data["data"]["free_time"]
                free_seconds = int(free_time["free_time"])
                send_free_time = int(free_time["send_freetime"])

                if send_free_time > 0:
                    ret_msg += t(
                        "games.cloud.success", game=self.game, time=send_free_time
                    )
                else:
                    if free_seconds < 600:
                        await asyncio.sleep(random.randint(3, 6))
                        _res = await http.get(url=self.url, headers=self.headers)
                        _data = await _res.json()
                        _free_time = _data["data"]["free_time"]
                        get_free_time = int(_free_time["free_time"]) - free_seconds
                        if get_free_time > 0:
                            ret_msg += t(
                                "games.cloud.success",
                                game=self.game,
                                time=get_free_time,
                            )
                        else:
                            ret_msg += t("games.cloud.limit_fail", game=self.game)
                    else:
                        ret_msg += t("games.cloud.limit_fail", game=self.game)
                log.info(ret_msg)

                time = tools.time_conversion(free_seconds)
                card_status = data["data"]["play_card"]["short_msg"]
                coin_num = data["data"]["coin"]["coin_num"]
                status_msg = t(
                    "games.cloud.status",
                    time=time,
                    card_status=card_status,
                    coin_name=self.coin_name,
                    coin=coin_num,
                )
                log.info(status_msg)
                ret_msg += "\t" + status_msg
            elif data["retcode"] == -100:
                ret_msg += t("games.cloud.token_invalid", game=self.game)
                log.warning(ret_msg)
                await self.clear_cookie_func()
            else:
                err_msg = await res.text()
                ret_msg += t("games.cloud.script_fail", game=self.game, error=err_msg)
                log.warning(ret_msg)

        except Exception as e:
            err_msg = t("games.cloud.exec_error", game=self.game, error=e)
            log.error(err_msg)
            ret_msg += err_msg
        return ret_msg


async def run_task() -> str:
    conf = config.config["cloud_games"]["cn"]
    log.info(t("games.cloud.start"))
    ret_msg = ""
    for game in CLOUD_GAMES:
        token = conf.get(game.name, {}).get("token")
        if conf.get(game.name, {}).get("enable") and token != "":
            game_task = CloudGame(
                t(f"games.names.{game.name}"),
                game.api,
                token,
                game.hostname,
                game.biz,
                t(f"games.cloud.{game.name}_coin"),
                functools.partial(clear_cookie, game.name),
            )
            ret_msg += await game_task.check_in() + "\n\n"

    return ret_msg
