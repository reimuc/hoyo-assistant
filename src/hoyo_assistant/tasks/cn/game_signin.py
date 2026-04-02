import asyncio
import random
from typing import Any, cast

from ...core import account, captcha, config, login, tools
from ...core.constants import (
    ACT_ID_CN_GENSHIN,
    ACT_ID_CN_HONKAI2,
    ACT_ID_CN_HONKAI3RD,
    ACT_ID_CN_HONKAI_SR,
    ACT_ID_CN_TEARS_OF_THEMIS,
    ACT_ID_CN_ZZZ,
    API_CN_GAME_CHECKIN_REWARDS,
    API_CN_GAME_IS_SIGN,
    API_CN_GAME_SIGN,
    API_ZZZ_GAME_CHECKIN_REWARDS,
    API_ZZZ_GAME_IS_SIGN,
    API_ZZZ_GAME_SIGN,
    MIHOYOBBS_CLIENT_TYPE_WEB,
    MIHOYOBBS_VERSION,
    REF_BH2_SIGN,
    REF_BH3_SIGN,
    REF_NXX_SIGN,
)
from ...core.error import CookieError
from ...core.i18n import t
from ...core.loghelper import log
from ...core.request import http


class GameCheckin:
    def __init__(
        self, game_id: str, game_mid: str, game_name: str, act_id: str, player_name: str
    ) -> None:
        """
        游戏签到

        :param game_id: 游戏ID(米游社)
        :param game_mid: 游戏ID(配置文件)
        :param game_name: 游戏名称
        :param act_id: 签到活动ID
        :param player_name: 玩家称呼
        """
        self.game_id = game_id
        self.game_mid = game_mid
        self.game_name = game_name
        self.act_id = act_id
        self.player_name = player_name
        self.headers: dict[str, Any] = {}

        self.set_headers()

        self.rewards_api = API_CN_GAME_CHECKIN_REWARDS
        self.profiles: list[Any] = []  # Initialize empty
        self.is_sign_api = API_CN_GAME_IS_SIGN

        self.sign_api = API_CN_GAME_SIGN
        self.checkin_rewards: list[Any] = []

    async def init(self) -> None:
        self.profiles = await account.get_account_list(self.game_id, self.headers)
        if len(self.profiles) != 0:
            self.checkin_rewards = await self.get_checkin_rewards()

    def set_headers(self) -> None:
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "DS": "",
            "Origin": "https://webstatic.mihoyo.com",
            "x-rpc-app_version": config.config.get("app_version", MIHOYOBBS_VERSION),
            "User-Agent": config.config["games"]["cn"]["useragent"],
            "x-rpc-client_type": MIHOYOBBS_CLIENT_TYPE_WEB,
            "Referer": "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?act_id="
            + self.act_id,
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,en-US;q=0.8",
            "X-Requested-With": "com.mihoyo.hyperion",
            "Cookie": config.config["account"]["cookie"],
            "x-rpc-device_id": config.config["device"]["id"],
        }

    async def get_award(self) -> list[Any]:
        log.info(t("games.cn.getting_rewards", name=self.game_name))
        req = await http.get(
            url=API_CN_GAME_CHECKIN_REWARDS,
            params={"act_id": self.act_id},
            headers=self.headers,
        )
        data = await req.json()
        if data["retcode"] == 0:
            return cast(list[Any], data["data"]["awards"])
        return []

    # 获取签到信息
    async def get_checkin_rewards(self) -> list[Any]:
        log.info(t("games.cn.getting_rewards", name=self.game_name))
        max_retry = 3
        for i in range(max_retry):
            try:
                response = await http.get(
                    API_CN_GAME_CHECKIN_REWARDS,
                    params={"act_id": self.act_id},
                    headers=self.headers,
                )
                data = await response.json()
                if data["retcode"] == 0:
                    return cast(list[Any], data["data"]["awards"])
                log.warning(t("games.cn.getting_rewards_retry", retry=i + 1))
            except Exception as e:
                log.warning(t("games.cn.getting_rewards_error", error=e, retry=i + 1))
            await asyncio.sleep(5)  # 等待5秒后重试
        log.warning(t("games.cn.getting_rewards_fail"))
        return []

    # 判断签到
    async def is_sign(self, region: str, uid: str, update: bool = False) -> Any:
        req = await http.get(
            url=API_CN_GAME_IS_SIGN,
            params={"act_id": self.act_id, "region": region, "uid": uid},
            headers=self.headers,
            use_cache=False,
        )
        data = await req.json()
        if data["retcode"] != 0:
            if not update and await login.update_cookie_token():
                self.set_headers()
                return await self.is_sign(region, uid, True)
            log.warning(t("games.cn.getting_info_fail"))
            log.debug(f"Response: {data}")
            raise CookieError(t("account.cookie_invalid"))
        return data["data"]

    async def check_in(self, profile: list[Any]) -> Any:
        header = self.headers.copy()
        retries = config.config["games"]["cn"].get("retries", 3)
        result = None
        for i in range(1, retries + 1):
            if i > 1:
                log.info(t("games.cn.captcha", retry=i, max=retries))
            # Use post method
            result = await http.post(
                url=self.sign_api,
                headers=header,
                json={"act_id": self.act_id, "region": profile[2], "uid": profile[1]},
            )
            if result.status == 429:  # aiohttp uses .status
                await asyncio.sleep(10)  # 429同ip请求次数过多，尝试sleep10s进行解决
                log.warning(t("games.cn.rate_limit"))
                continue
            data = await result.json()
            if data["retcode"] == 0 and data["data"]["success"] == 1 and i < retries:
                captcha_result = captcha.game_captcha(
                    data["data"]["gt"], data["data"]["challenge"]
                )
                if captcha_result is not None:
                    challenge = data["data"]["challenge"]
                    if isinstance(captcha_result, dict):
                        validate = captcha_result["validate"]
                        challenge = captcha_result["challenge"]
                    else:
                        # mypy may report unreachable here; ignore in task code
                        validate = captcha_result  # type: ignore[unreachable]
                    header.update(
                        {
                            "x-rpc-challenge": challenge,
                            "x-rpc-validate": validate,
                            "x-rpc-seccode": f"{validate}|jordan",
                        }
                    )
                await asyncio.sleep(random.randint(6, 15))
            else:
                break
        return result

    async def sign_account(self) -> str:
        return_data = f"{self.game_name}: "
        if not self.profiles:
            log.warning(t("games.cn.no_account", name=self.game_name))
            return_data += t("games.cn.no_account_msg", name=self.game_name)
            return return_data
        for profile in self.profiles:
            if profile[1] in config.config["games"]["cn"][self.game_mid]["black_list"]:
                log.info(t("games.cn.blacklisted", uid=profile[1]))
                continue
            log.info(t("games.cn.checkin_start", name=profile[0]))
            await asyncio.sleep(random.randint(2, 8))
            is_data = await self.is_sign(region=profile[2], uid=profile[1])
            if not isinstance(is_data, dict):
                log.warning(t("games.cn.getting_info_fail"))
                return_data += t("games.cn.sign_fail_account", uid=profile[0])
                continue
            if is_data.get("first_bind", False):
                log.warning(
                    t("games.cn.first_bind", name=self.player_name, uid=profile[0])
                )
                continue
            sign_days = is_data["total_sign_day"] - 1
            if is_data["is_sign"]:
                reward_item = tools.get_item(self.checkin_rewards[sign_days])
                log.info(
                    t(
                        "games.cn.checkin_already",
                        name=self.player_name,
                        uid=profile[0],
                        reward=reward_item,
                    )
                )
                sign_days += 1
            else:
                await asyncio.sleep(random.randint(2, 8))
                req = await self.check_in(profile)
                if req is None:
                    log.warning(
                        t(
                            "games.cn.checkin_fail",
                            name=self.player_name,
                            uid=profile[0],
                            reason="Unknown",
                        )
                    )
                    return_data += t("games.cn.sign_fail_account", uid=profile[0])
                    continue
                if req.status != 429:
                    data = await req.json()
                    payload = data.get("data") if isinstance(data, dict) else None
                    payload_success = (
                        payload.get("success") if isinstance(payload, dict) else None
                    )
                    if data.get("retcode") == 0 and payload_success == 0:
                        reward_item = tools.get_item(
                            self.checkin_rewards[0 if sign_days == 0 else sign_days + 1]
                        )
                        log.info(
                            t(
                                "games.cn.checkin_success",
                                name=self.player_name,
                                uid=profile[0],
                                reward=reward_item,
                            )
                        )
                        sign_days += 2
                    elif data.get("retcode") == -5003:
                        reward_item = tools.get_item(self.checkin_rewards[sign_days])
                        log.info(
                            t(
                                "games.cn.checkin_already",
                                name=self.player_name,
                                uid=profile[0],
                                reward=reward_item,
                            )
                        )
                    else:
                        s = t("games.cn.sign_fail_msg")
                        if (
                            payload not in (None, "")
                            and isinstance(payload, dict)
                            and payload.get("success", -1)
                        ):
                            s += (
                                f"{t('games.cn.captcha_trigger')}\njson info: "
                                + await req.text()
                            )
                        log.warning(s)
                        return_data += t("games.cn.sign_fail_captcha", uid=profile[0])
                        continue
                else:
                    return_data += t("games.cn.sign_fail_account", uid=profile[0])
                    continue

            reward_item_final = tools.get_item(self.checkin_rewards[sign_days - 1])
            return_data += t(
                "games.cn.sign_success_msg",
                uid=profile[0],
                days=sign_days,
                reward=reward_item_final,
            )
        return return_data


class Honkai2(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "bh2_cn",
            "honkai2",
            t("games.names.honkai2"),
            ACT_ID_CN_HONKAI2,
            t("games.titles.honkai2"),
        )
        self.headers["Referer"] = (
            f"{REF_BH2_SIGN}?bbs_auth_required"
            f"=true&act_id={ACT_ID_CN_HONKAI2}&bbs_presentation_style=fullscreen"
            "&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
        )


class Honkai3rd(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "bh3_cn",
            "honkai3rd",
            t("games.names.honkai3rd"),
            ACT_ID_CN_HONKAI3RD,
            t("games.titles.honkai3rd"),
        )
        self.headers["Referer"] = (
            f"{REF_BH3_SIGN}?bbs_auth_required"
            f"=true&act_id={ACT_ID_CN_HONKAI3RD}&bbs_presentation_style=fullscreen"
            "&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
        )


class TearsOfThemis(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "nxx_cn",
            "tears_of_themis",
            t("games.names.tears_of_themis"),
            ACT_ID_CN_TEARS_OF_THEMIS,
            t("games.titles.tears_of_themis"),
        )
        self.headers["Referer"] = (
            f"{REF_NXX_SIGN}?bbs_auth_required=true&bbs_presentation_style=fullscreenact_id={ACT_ID_CN_TEARS_OF_THEMIS}"
        )


class Genshin(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "hk4e_cn",
            "genshin",
            t("games.names.genshin"),
            ACT_ID_CN_GENSHIN,
            t("games.titles.genshin"),
        )
        self.headers["Origin"] = "https://act.mihoyo.com"
        self.headers["x-rpc-signgame"] = "hk4e"
        # self.init() # Removed


class Honkaisr(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "hkrpg_cn",
            "honkai_sr",
            t("games.names.honkai_sr"),
            ACT_ID_CN_HONKAI_SR,
            t("games.titles.honkai_sr"),
        )
        self.headers["Origin"] = "https://act.mihoyo.com"
        # self.init() # Removed


class ZZZ(GameCheckin):
    def __init__(self) -> None:
        super().__init__(
            "nap_cn", "zzz", t("games.names.zzz"), ACT_ID_CN_ZZZ, t("games.titles.zzz")
        )
        self.headers["Origin"] = "https://act.mihoyo.com"
        self.headers["X-Rpc-Signgame"] = "zzz"
        self.rewards_api = API_ZZZ_GAME_CHECKIN_REWARDS
        self.is_sign_api = API_ZZZ_GAME_IS_SIGN
        self.sign_api = API_ZZZ_GAME_SIGN
        # self.init() # Removed


async def checkin_game(
    game_name: str, game_module: type, game_print_name: str = ""
) -> str:
    game_config = config.config["games"]["cn"][game_name]
    if game_config["checkin"]:
        await asyncio.sleep(random.randint(2, 8))
        if game_print_name == "":
            game_print_name = game_name
        log.info(t("games.cn.checkin_start", name=game_print_name))
        instance = game_module()
        await instance.init()
        return_data = f"\n\n{await instance.sign_account()}"
        return return_data
    return ""


async def run_task() -> str:
    games = [
        (t("games.names.honkai2"), "honkai2", Honkai2),
        (t("games.names.honkai3rd"), "honkai3rd", Honkai3rd),
        (t("games.names.tears_of_themis"), "tears_of_themis", TearsOfThemis),
        (t("games.names.genshin"), "genshin", Genshin),
        (t("games.names.honkai_sr"), "honkai_sr", Honkaisr),
        (t("games.names.zzz"), "zzz", ZZZ),
    ]
    return_data = ""
    for game_print_name, game_name, game_module in games:
        return_data += await checkin_game(game_name, game_module, game_print_name)
    return return_data
