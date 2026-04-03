"""Base class for cloud game sign-in tasks."""

import asyncio
import random
from collections.abc import Callable
from typing import Any

from ...core import http, log, t, tools


class BaseCloudGame:
    """Base class for cloud game sign-in functionality."""

    def __init__(
        self,
        game: str,
        url: str,
        coin_name: str,
        clear_cookie_func: Callable[[], Any],
        headers: dict[str, str],
    ) -> None:
        self.game = game
        self.url = url
        self.coin_name = coin_name
        self.clear_cookie_func = clear_cookie_func
        self.headers = headers

    async def check_in(self, *, retry_on_limit: bool = False) -> str:
        """Perform cloud game sign-in.

        Args:
            retry_on_limit: Whether to retry when limit not reached (CN specific).
        """
        log.info(t("games.cloud.checkin_start", game=self.game))
        ret_msg = ""

        try:
            res = await http.get(url=self.url, headers=self.headers)
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
                    if retry_on_limit and free_seconds < 600:
                        # CN-specific retry logic
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
