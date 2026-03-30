from typing import Any

from . import config, login
from .constants import API_ACCOUNT_INFO, GAME_INFO_ID_TO_CONFIG, GAME_INFO_ID_TO_NAME
from .error import CookieError
from .i18n import t
from .loghelper import log
from .request import http


# Helper
def get_game_name(game_id: str) -> str:
    config_name = GAME_INFO_ID_TO_CONFIG.get(game_id)
    if config_name:
        if config_name == "honkaisr":
            config_name = "honkai_sr"
        return t(
            f"games.names.{config_name}",
            default=GAME_INFO_ID_TO_NAME.get(game_id, game_id),
        )
    return GAME_INFO_ID_TO_NAME.get(game_id, game_id)


async def get_account_list(
    game_id: str, headers: dict[str, Any], update: bool = False
) -> list[tuple[str, str, str]]:
    """
    获取账号列表

    :param game_id: 游戏ID
    :param headers: 请求头
    :param update: 是否已尝试更新Cookie

    :return: 账号列表
    """
    game_name = get_game_name(game_id)

    if update and await login.update_cookie_token():
        headers["Cookie"] = config.config["account"]["cookie"]
    elif update:
        log.warning(t("account.list_fail", name=game_name))
        raise CookieError(t("account.cookie_invalid"))

    log.info(t("account.fetching", name=game_name))
    response = await http.get(
        API_ACCOUNT_INFO, params={"game_biz": game_id}, headers=headers, use_cache=False
    )
    data = await response.json()
    if data["retcode"] == -100:
        return await get_account_list(game_id, headers, update=True)

    if data["retcode"] != 0:
        log.warning(t("account.list_fail", name=game_name))
        return []

    account_list: list[tuple[str, str, str]] = []
    for i in data["data"]["list"]:
        account_list.append((i["nickname"], i["game_uid"], i["region"]))

    if len(account_list) == 0:
        if not update:
            return await get_account_list(game_id, headers, True)
        log.warning(t("account.cookie_error_game", name=game_name))
        return []

    log.info(t("account.list_success", count=len(account_list), name=game_name))
    return account_list
