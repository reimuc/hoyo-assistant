import asyncio
import json
import random
from copy import deepcopy
from typing import Any, cast

from ...core import captcha, config, login, tools
from ...core.constants import (
    API_BBS_CAPTCHA_VERIFY,
    API_BBS_GET_CAPTCHA,
    API_BBS_LIKE,
    API_BBS_POST_DETAIL,
    API_BBS_POST_LIST,
    API_BBS_SHARE,
    API_BBS_SIGN,
    API_BBS_TASKS_LIST,
    MIHOYOBBS_CLIENT_TYPE,
    MIHOYOBBS_POST_TYPES,
    MIHOYOBBS_VERIFY_KEY,
    MIHOYOBBS_VERSION,
)
from ...core.error import StokenError
from ...core.i18n import t
from ...core.loghelper import log
from ...core.request import http


async def wait() -> None:
    await asyncio.sleep(random.randint(3, 8))


class Mihoyobbs:
    def __init__(self) -> None:
        self.today_get_coins = 0
        self.today_have_get_coins = 0
        self.have_coins = 0
        self.bbs_config = config.config["mihoyobbs"]
        # 明确标注 bbs_list 类型以便 mypy 能识别为不包含 None 的字典列表
        tmp_list: list[dict[str, Any]] = []
        for i in self.bbs_config["checkin_list"]:
            val = MIHOYOBBS_POST_TYPES.get(i)
            if val is not None:
                tmp_list.append(cast(dict[str, Any], val))
        self.bbs_list: list[dict[str, Any]] = tmp_list
        self.headers = {
            "DS": tools.get_ds(web=False),
            "cookie": login.get_stoken_cookie(),
            "x-rpc-client_type": MIHOYOBBS_CLIENT_TYPE,
            "x-rpc-app_version": MIHOYOBBS_VERSION,
            "x-rpc-sys_version": "12",
            "x-rpc-channel": "miyousheluodi",
            "x-rpc-device_id": config.config["device"]["id"],
            "x-rpc-device_name": config.config["device"]["name"],
            "x-rpc-device_model": config.config["device"]["model"],
            "x-rpc-h265_supported": "1",
            "Referer": "https://app.mihoyo.com",
            "x-rpc-verify_key": MIHOYOBBS_VERIFY_KEY,
            "x-rpc-csm_source": "discussion",
            "Content-Type": "application/json; charset=UTF-8",
            "Host": "bbs-api.miyoushe.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/4.9.3",
        }
        self.task_header = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://webstatic.mihoyo.com",
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/{MIHOYOBBS_VERSION}",
            "Referer": "https://webstatic.mihoyo.com",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,en-US;q=0.8",
            "X-Requested-With": "com.mihoyo.hyperion",
            "Cookie": config.config.get("account", {}).get("cookie", ""),
        }
        if config.config["device"]["fp"] != "":
            self.headers["x-rpc-device_fp"] = config.config["device"]["fp"]
        self.task_do = {
            "sign": False,
            "read": False,
            "read_num": 3,
            "like": False,
            "like_num": 5,
            "share": False,
        }
        self.postsList: list[list[Any]] = []

    async def init(self) -> None:
        await self.get_tasks_list()
        # 如果这三个任务都做了就没必要获取帖子了
        if self.task_do["read"] and self.task_do["like"] and self.task_do["share"]:
            pass
        else:
            self.postsList = await self.get_list()

    async def refresh_list(self) -> None:
        self.postsList = await self.get_list()

    def get_max_req_post_num(self) -> int:
        return max(self.task_do["read_num"], self.task_do["like_num"])

    async def get_pass_challenge(self) -> str | None:
        req = await http.get(url=API_BBS_GET_CAPTCHA, headers=self.headers)
        data = await req.json()
        if data["retcode"] != 0:
            return None
        captcha_result = captcha.bbs_captcha(
            data["data"]["gt"], data["data"]["challenge"]
        )
        if captcha_result is not None:
            challenge = data["data"]["challenge"]
            if isinstance(captcha_result, dict):
                validate = captcha_result["validate"]
                challenge = captcha_result["challenge"]
            else:
                # mypy may have trouble inferring types here; keep as-is
                validate = captcha_result  # type: ignore[unreachable]

            check_req = await http.post(
                url=API_BBS_CAPTCHA_VERIFY,
                headers=self.headers,
                json={
                    "geetest_challenge": challenge,
                    "geetest_seccode": validate + "|jordan",
                    "geetest_validate": validate,
                },
            )
            check = await check_req.json()
            if check["retcode"] == 0:
                return cast(str, check["data"]["challenge"])
        return None

    # 获取任务列表，用来判断做了哪些任务
    async def get_tasks_list(self, update: bool = False) -> None:
        log.info(t("mihoyobbs.get_tasks"))
        req = await http.get(
            url=API_BBS_TASKS_LIST,
            params={"point_sn": "myb"},
            headers=self.task_header,
            use_cache=False,
        )
        data = await req.json()
        if "err" in data["message"] or data["retcode"] == -100:
            if not update and await login.update_cookie_token():
                self.task_header["Cookie"] = config.config["account"]["cookie"]
                return await self.get_tasks_list(True)
            else:
                log.error(t("mihoyobbs.get_tasks_fail"))
                await config.clear_cookie()
                raise StokenError(t("account.stoken_error"))
        self.today_get_coins = data["data"]["can_get_points"]
        self.today_have_get_coins = data["data"]["already_received_points"]
        self.have_coins = data["data"]["total_points"]
        tasks = {
            58: {"attr": "sign", "done": "is_get_award"},
            59: {"attr": "read", "done": "is_get_award", "num_attr": "read_num"},
            60: {"attr": "like", "done": "is_get_award", "num_attr": "like_num"},
            61: {"attr": "share", "done": "is_get_award"},
        }
        if self.today_get_coins == 0:
            self.task_do["sign"] = True
            self.task_do["read"] = True
            self.task_do["like"] = True
            self.task_do["share"] = True
        else:
            missions = data["data"]["states"]
            for task in tasks:
                mission_state = next(
                    (x for x in missions if x["mission_id"] == task), None
                )
                if mission_state is None:
                    continue
                do = tasks[task]
                if mission_state[do["done"]]:
                    self.task_do[do["attr"]] = True
                elif do.get("num_attr") is not None:
                    self.task_do[do["num_attr"]] = (
                        self.task_do[do["num_attr"]] - mission_state["happened_times"]
                    )
        if data["data"]["can_get_points"] != 0:
            if len(data["data"]["states"]) == 0:
                log.info(t("mihoyobbs.coins_today", coins=self.today_get_coins))
            else:
                new_day = data["data"]["states"][0]["mission_id"] >= 62
                if new_day:
                    log.info(t("mihoyobbs.coins_new_day", coins=self.today_get_coins))
                else:
                    log.info(t("mihoyobbs.coins_remain", coins=self.today_get_coins))

    # 获取要帖子列表
    async def get_list(self) -> list[list[Any]]:
        # 类型注解，列表内为 [post_id, subject]
        choice_post_list: list[list[Any]] = []
        log.info(t("mihoyobbs.get_posts"))
        req = await http.get(
            url=API_BBS_POST_LIST,
            params={
                "forum_id": self.bbs_list[0]["forumId"],
                "is_good": str(False).lower(),
                "is_hot": str(False).lower(),
                "page_size": 20,
                "sort_type": 1,
            },
            headers=self.headers,
            use_cache=False,
        )
        data = (await req.json())["data"]["list"]
        while len(choice_post_list) < self.get_max_req_post_num():
            post = random.choice(data)
            if post["post"]["subject"] not in [x[1] for x in choice_post_list]:
                choice_post_list.append(
                    [post["post"]["post_id"], post["post"]["subject"]]
                )
        log.info(t("mihoyobbs.posts_count", count=len(choice_post_list)))
        return choice_post_list

    # 进行签到操作
    async def signing(self) -> None:
        if self.task_do["sign"]:
            log.info(t("mihoyobbs.task_done"))
            return
        log.info(t("mihoyobbs.signing"))
        header = self.headers.copy()
        for forum in self.bbs_list:
            challenge = None
            for _retry_count in range(2):
                post_data = json.dumps({"gids": forum["id"]})
                # post_data.replace(' ', '') # This line does nothing as strings are immutable and result is ignored
                post_data = post_data.replace(" ", "")
                header["DS"] = tools.get_ds2(
                    "", post_data
                )  # DS2 might be CPU bound but okay
                req = await http.post(url=API_BBS_SIGN, data=post_data, headers=header)
                log.debug(await req.text())
                data = await req.json()
                if data["retcode"] == 1034:
                    log.warning(t("mihoyobbs.sign_captcha"))
                    challenge = await self.get_pass_challenge()
                    if challenge is not None:
                        header["x-rpc-challenge"] = challenge
                elif "err" not in data["message"] and data["retcode"] == 0:
                    log.info(
                        t(
                            "mihoyobbs.sign_success",
                            forum=forum["name"],
                            message=data.get("message", "OK"),
                        )
                    )
                    await wait()
                    break
                elif data["retcode"] == -100:
                    log.error(t("mihoyobbs.sign_cookie_expired"))
                    await config.clear_stoken()
                    raise StokenError(t("account.stoken_error"))
                else:
                    log.error(t("mihoyobbs.sign_unknown_error", error=await req.text()))
            if challenge is not None:
                header.pop("x-rpc-challenge")

    # 看帖子
    async def read_posts(self, post_info: list[Any]) -> None:
        req = await http.get(
            url=API_BBS_POST_DETAIL,
            params={"post_id": post_info[0]},
            headers=self.headers,
        )
        log.debug(await req.text())
        data = await req.json()
        if data["message"] == "OK":
            log.debug(t("mihoyobbs.read_success", title=post_info[1]))

    # 点赞
    async def like_posts(self, post_info: list[Any], captcha_try: bool = False) -> bool:
        header = deepcopy(self.headers)
        if captcha_try:
            challenge = await self.get_pass_challenge()
            if challenge is not None:
                header["x-rpc-challenge"] = challenge
            else:
                # 验证码没通过
                await wait()
        req = await http.post(
            url=API_BBS_LIKE,
            headers=header,
            json={"post_id": post_info[0], "is_cancel": False},
        )
        log.debug(await req.text())
        data = await req.json()
        if data["message"] == "OK":
            log.debug(t("mihoyobbs.like_success", title=post_info[1]))
            # 判断取消点赞是否打开
            if self.bbs_config["cancel_like"]:
                await wait()
                await self.cancel_like_post(post_info)
            return True
        elif data["retcode"] == 1034 and not captcha_try:
            log.warning(t("mihoyobbs.like_captcha"))
            return await self.like_posts(post_info, True)
        else:
            log.error(t("mihoyobbs.like_fail", error=await req.text()))
        return False

    # 取消点赞
    async def cancel_like_post(self, post_info: list[Any]) -> bool:
        req = await http.post(
            url=API_BBS_LIKE,
            headers=self.headers,
            json={"post_id": post_info[0], "is_cancel": True},
        )
        if (await req.json())["message"] == "OK":
            log.debug(t("mihoyobbs.unlike_success", title=post_info[1]))
            return True
        return False

    # 分享操作
    async def share_post(self, post_info: list[Any]) -> None:
        for i in range(3):
            req = await http.get(
                url=API_BBS_SHARE,
                params={"entity_id": post_info[0], "entity_type": 1},
                headers=self.headers,
            )
            log.debug(await req.text())
            data = await req.json()
            if data["message"] == "OK":
                log.debug(t("mihoyobbs.share_success", title=post_info[1]))
                break
            log.debug(t("mihoyobbs.share_retry", retry=i + 2))
            await wait()

    async def post_task(self) -> None:
        log.info(t("mihoyobbs.post_task_start"))
        if self.task_do["read"] and self.task_do["like"] and self.task_do["share"]:
            log.info(t("mihoyobbs.post_task_done"))
            return
        # 执行帖子的阅读 点赞 和 分享，其中阅读是必完成的
        for post in self.postsList:
            if (
                self.bbs_config["read"]
                and not self.task_do["read"]
                and self.task_do["read_num"] > 0
            ):
                await self.read_posts(post)
                self.task_do["read_num"] -= 1
                await wait()
            if (
                self.bbs_config["like"]
                and not self.task_do["like"]
                and self.task_do["like_num"] > 0
            ):
                await self.like_posts(post)
                self.task_do["like_num"] -= 1
                await wait()
            if self.bbs_config["share"] and not self.task_do["share"]:
                await self.share_post(post)
                self.task_do["share"] = True
                await wait()

    async def run_task(self) -> str:
        await self.init()  # Ensure initialized
        return_data = "米游社: "
        if (
            self.task_do["sign"]
            and self.task_do["read"]
            and self.task_do["like"]
            and self.task_do["share"]
        ):
            return_data += t(
                "mihoyobbs.summary_done",
                got=self.today_have_get_coins,
                total=self.have_coins,
            )
            log.info(
                t(
                    "mihoyobbs.summary_done",
                    got=self.today_have_get_coins,
                    total=self.have_coins,
                )
            )
            return return_data
        i = 0
        while self.today_get_coins != 0 and i < 2:
            if i > 0:
                await wait()
                await self.refresh_list()
            if self.bbs_config["checkin"]:
                await self.signing()
            await self.post_task()
            await self.get_tasks_list()
            i += 1
        return_data += t(
            "mihoyobbs.summary_remain",
            got=self.today_have_get_coins,
            can_get=self.today_get_coins,
            total=self.have_coins,
        )
        log.info(
            t(
                "mihoyobbs.summary_remain",
                got=self.today_have_get_coins,
                can_get=self.today_get_coins,
                total=self.have_coins,
            )
        )
        await wait()
        return return_data
