import re
from copy import deepcopy
from typing import cast

from . import config
from .constants import (
    API_BBS_GET_COOKIE_TOKEN,
    API_BBS_GET_MULTI_TOKEN,
    API_GET_HK4E_TOKEN,
    API_GET_TOKEN_BY_STOKEN,
    DEFAULT_HEADERS,
)
from .error import CookieError, StokenError
from .i18n import t
from .loghelper import log
from .request import http

headers = deepcopy(DEFAULT_HEADERS)
headers.pop("DS")
headers.pop("Origin")
headers.pop("Referer")


async def login() -> None:
    if not config.config["account"]["cookie"]:
        await config.clear_cookie()
        raise CookieError(t("account.missing_cookie"))

    if config.config["account"]["stoken"] == "":
        raise StokenError(t("account.missing_stoken"))
    uid = get_uid()
    if uid is None:
        await config.clear_cookie()
        raise CookieError(t("account.missing_uid"))
    config.config["account"]["stuid"] = uid
    if require_mid():
        config.config["account"]["mid"] = get_mid()
    log.info(t("account.login_ok"))
    log.info(t("account.saving_config"))
    await config.save_config()

    # 获取 cookie_token
    if require_cookie_token():
        log.info(t("account.fetching_cookie_token"))
        req = await http.get(
            API_GET_TOKEN_BY_STOKEN,
            params={"uid": uid, "stoken": config.config["account"]["stoken"]},
        )
        data = await req.json()
        if data["retcode"] != 0:
            await config.clear_stoken()
            raise StokenError(t("account.stoken_invalid"))
        config.config["account"]["cookie"] += (
            f" cookie_token={data['data']['token']['token']};"
        )
        log.info(t("account.cookie_token_ok"))

    # 获取 stoken
    if require_stoken():
        log.info(t("account.fetching_stoken"))
        req = await http.get(
            API_BBS_GET_COOKIE_TOKEN,
            params={"uid": uid, "stoken": config.config["account"]["stoken"]},
        )
        data = await req.json()
        if data["retcode"] != 0:
            await config.clear_stoken()
            raise StokenError(t("account.stoken_fetch_fail"))
        log.info(t("account.stoken_ok"))

    # 刷新 cookie
    if require_cookie_token() and require_stoken():
        log.info(t("account.refreshing_cookie"))
        req = await http.get(
            API_BBS_GET_MULTI_TOKEN,
            params={
                "uid": uid,
                "token_types": "3",
                "login_ticket": config.config["account"]["login_ticket"],
            },
        )
        data = await req.json()
        if data["retcode"] != 0:
            await config.clear_cookie()
            raise CookieError(t("account.cookie_refresh_fail"))
        log.info(t("account.cookie_refresh_ok"))


def get_login_ticket() -> str | None:
    ticket_match = re.search(
        r"login_ticket=(.*?)(?:;|$)", str(config.config["account"]["cookie"])
    )
    return ticket_match.group(1) if ticket_match else None


def get_mid() -> str | None:
    mid = re.search(
        r"(account_mid_v2|ltmid_v2|mid)=(.*?)(?:;|$)",
        str(config.config["account"]["cookie"]),
    )
    return mid.group(2) if mid else None


def get_uid() -> str | None:
    uid: str | None = None
    uid_match = re.search(
        r"(account_id|ltuid|login_uid|ltuid_v2|account_id_v2)=(\d+)",
        config.config["account"]["cookie"],
    )
    if uid_match is None:
        return uid
    uid = uid_match.group(2)
    return uid


async def get_stoken(login_ticket: str, uid: str) -> str:
    response = await http.get(
        url=API_BBS_GET_MULTI_TOKEN,
        params={"login_ticket": login_ticket, "token_types": "3", "uid": uid},
        headers=headers,
    )
    data = await response.json()
    if data["retcode"] == 0:
        return cast(str, data["data"]["list"][0]["token"])
    else:
        log.error(t("account.login_ticket_expired"))
        await config.clear_cookie()
        raise CookieError(t("account.cookie_invalid"))


async def get_cookie_token_by_stoken() -> str:
    if (
        config.config["account"]["stoken"] == ""
        and config.config["account"]["stuid"] == ""
    ):
        log.error(t("account.stoken_suid_empty"))
        await config.clear_cookie()
        raise CookieError(t("account.cookie_invalid"))
    header = deepcopy(headers)
    header["cookie"] = get_stoken_cookie()
    response = await http.get(url=API_BBS_GET_COOKIE_TOKEN, headers=header)
    data = await response.json()
    if data.get("retcode", -1) != 0:
        log.error(t("account.stoken_fetch_fail"))
        await config.clear_stoken()
        raise StokenError(t("account.stoken_error"))
    return cast(str, data["data"]["cookie_token"])


async def update_cookie_token() -> bool:
    log.info(t("account.cookie_refresh_start"))
    if str(config.config["account"]["stoken"]) == "":
        log.warning(t("account.no_stoken_cant_refresh"))
        return False
    old_token_match = re.search(
        r"cookie_token=(.*?)(?:;|$)", config.config["account"]["cookie"]
    )
    if old_token_match:
        new_token = await get_cookie_token_by_stoken()
        log.info(t("account.cookie_token_refresh_ok"))
        config.config["account"]["cookie"] = config.config["account"]["cookie"].replace(
            old_token_match.group(1), new_token
        )
        await config.save_config()
        return True
    # 更新 cookie_token
    req = await http.get(
        API_GET_TOKEN_BY_STOKEN,
        params={
            "uid": config.config["account"]["stuid"],
            "stoken": config.config["account"]["stoken"],
        },
    )
    data = await req.json()
    if data["retcode"] != 0:
        log.error(t("account.stoken_invalid"))
        await config.clear_stoken()
        return False
    config.config["account"]["cookie"] += (
        f" cookie_token={data['data']['token']['token']};"
    )
    await config.save_config()
    return True


def require_mid() -> bool:
    """
    判断是否需要mid

    :return: 是否需要mid
    """
    return str(config.config["account"]["stoken"]).startswith("v2_")


def get_stoken_cookie() -> str:
    """
    获取带stoken的cookie

    :return: 正确的stoken的cookie
    """
    cookie = f"stuid={config.config['account']['stuid']};stoken={config.config['account']['stoken']}"
    if require_mid():
        if config.config["account"]["mid"]:
            cookie += f";mid={config.config['account']['mid']}"
        else:
            log.error(t("account.mid_required"))
            raise CookieError(t("account.cookie_invalid"))
    return cookie


def require_cookie_token() -> bool:
    """
    判断是否需要 cookie_token

    :return: 是否需要 cookie_token
    """
    return str(config.config["account"]["stoken"]).startswith("v2_")


def require_stoken() -> bool:
    """
    判断是否需要 stoken

    :return: 是否需要 stoken
    """
    return str(config.config["account"]["stoken"]).startswith("v1_")


async def get_hk4e_token(game_uid: str, region: str) -> str:
    log.info(t("account.fetching_hk4e_token"))
    req = await http.post(
        API_GET_HK4E_TOKEN,
        json={
            "game_biz": "hk4e_cn",
            "region": region,
            "uid": game_uid,
            "stoken": config.config["account"]["stoken"],
        },
    )
    data = await req.json()
    if data["retcode"] != 0:
        log.error(t("account.hk4e_token_fail"))
        raise CookieError(t("account.cookie_invalid"))
    return cast(str, data["data"]["token"])
