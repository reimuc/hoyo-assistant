import asyncio
import random

from ...core import config
from ...core.constants import (
    ACT_ID_OS_GENSHIN,
    ACT_ID_OS_HONKAI3RD,
    ACT_ID_OS_HONKAI_SR,
    ACT_ID_OS_TEARS_OF_THEMIS,
    ACT_ID_OS_ZZZ,
    API_OS_ACT,
    API_OS_ACT_HI3,
    API_OS_ACT_HSR,
    API_OS_ACT_ZZZ,
    API_OS_REFERER,
)
from ...core.i18n import t
from ...core.loghelper import log
from ...core.request import http

RET_CODE_ALREADY_SIGNED_IN = -5003


async def hoyo_checkin(event_base_url: str, act_id: str, game_name: str) -> str:
    """
    国际服游戏签到

    :param event_base_url: 基础Url
    :param act_id: 活动id
    :param game_name: 游戏名称
    :return: 签到结果
    """
    os_lang = config.config["games"]["os"]["lang"]
    reward_url = f"{event_base_url}/home?lang={os_lang}&act_id={act_id}"
    info_url = f"{event_base_url}/info?lang={os_lang}&act_id={act_id}"
    sign_url = f"{event_base_url}/sign?lang={os_lang}"

    cookie_str = config.config.get("games", {}).get("os", {}).get("cookie", "")

    headers = {
        "Referer": API_OS_REFERER,
        "Accept-Encoding": "gzip, deflate, br",
        "Cookie": cookie_str,
    }
    if act_id == ACT_ID_OS_ZZZ:
        headers["x-rpc-signgame"] = "zzz"

    log.info(t("games.os.checkin_start", game=game_name))

    resp = await http.get(info_url, headers=headers, use_cache=False)
    info_list = await resp.json()

    today = info_list.get("data", {}).get("today")
    total_sign_in_day = info_list.get("data", {}).get("total_sign_day")
    already_signed_in = info_list.get("data", {}).get("is_sign")
    first_bind = info_list.get("data", {}).get("first_bind")

    if already_signed_in:
        ret_msg = t("games.os.checkin_already", game=game_name)
        log.info(ret_msg)
        return ret_msg

    if first_bind:
        ret_msg = t("games.os.manual_checkin", game=game_name)
        log.info(ret_msg)
        return ret_msg

    resp_awards = await http.get(reward_url, headers=headers, use_cache=False)
    awards_data = await resp_awards.json()

    awards = awards_data.get("data", {}).get("awards")

    log.info(t("games.os.preparing", today=today))

    # a normal human can't instantly click, so we wait a bit
    sleep_time = random.uniform(2.0, 10.0)
    log.debug(t("games.os.waiting", time=sleep_time))
    await asyncio.sleep(sleep_time)

    resp_sign = await http.post(sign_url, headers=headers, json={"act_id": act_id})
    response = await resp_sign.json()

    code = response.get("retcode", 99999)

    log.debug(t("games.os.return_code", code=code))

    reward = awards[total_sign_in_day - 1]
    days = total_sign_in_day + 1

    if code == RET_CODE_ALREADY_SIGNED_IN:
        ret_msg = t("games.os.checkin_already", game=game_name)
        log.info(ret_msg)
        return ret_msg
    elif code != 0:
        reason = response.get("message", "Unknown error")
        ret_msg = t("games.os.checkin_fail", game=game_name, reason=reason)
        log.error(ret_msg)
        return ret_msg

    log.info(
        t(
            "games.os.checkin_success",
            game=game_name,
            name=reward["name"],
            count=reward["cnt"],
        )
    )

    ret_msg = t(
        "games.os.sign_success_msg",
        game=game_name,
        days=days,
        name=reward["name"],
        count=reward["cnt"],
    )
    return ret_msg


async def run_task() -> str:
    log.info(t("games.os.start"))
    ret_parts: list[str] = []
    # Genshin
    if config.config["games"]["os"].get("genshin", {}).get("checkin"):
        ret_parts.append(
            await hoyo_checkin(API_OS_ACT, ACT_ID_OS_GENSHIN, t("games.names.genshin"))
        )
    # HSR
    if config.config["games"]["os"].get("honkai_sr", {}).get("checkin"):
        ret_parts.append(
            await hoyo_checkin(
                API_OS_ACT_HSR, ACT_ID_OS_HONKAI_SR, t("games.names.honkai_sr")
            )
        )
    # HI3
    if config.config["games"]["os"].get("honkai3rd", {}).get("checkin"):
        ret_parts.append(
            await hoyo_checkin(
                API_OS_ACT_HI3, ACT_ID_OS_HONKAI3RD, t("games.names.honkai3rd")
            )
        )
    # ToT
    if config.config["games"]["os"].get("tears_of_themis", {}).get("checkin"):
        ret_parts.append(
            await hoyo_checkin(
                API_OS_ACT, ACT_ID_OS_TEARS_OF_THEMIS, t("games.names.tears_of_themis")
            )
        )
    # ZZZ
    if config.config["games"]["os"].get("zzz", {}).get("checkin"):
        ret_parts.append(
            await hoyo_checkin(API_OS_ACT_ZZZ, ACT_ID_OS_ZZZ, t("games.names.zzz"))
        )

    return "\t".join(part for part in ret_parts if part)
