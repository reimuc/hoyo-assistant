import asyncio
import base64
import hashlib
import hmac
import inspect
import os
import re
import time
from configparser import ConfigParser, NoOptionError
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote_plus

from . import config as runtime_config
from .i18n import t
from .loghelper import log
from .request import http


def get_push_title(status_id: int) -> str:
    """
    获取推送标题
    :param status_id: 状态ID
    :return:
    """
    status_map = {
        -99: "push.status_missing_dep",
        -2: "push.status_error_id",
        -1: "push.status_config_update",
        0: "push.status_success",
        1: "push.status_fail",
        2: "push.status_partial_fail",
        3: "push.status_captcha",
    }
    key = status_map.get(status_id, "push.status_unknown")
    return t(key)


class PushHandler:
    def __init__(self, config_file: str = "push.ini") -> None:
        self.http = http  # Use global async http
        self.cfg = ConfigParser()
        # If config_file is an absolute path, use it directly.
        # Otherwise, default to CWD/config directory.
        if os.path.isabs(config_file):
            self.config_path = os.path.dirname(config_file)
            self.config_name = os.path.basename(config_file)
        else:
            self.config_path = os.path.join(os.getcwd(), "config")
            self.config_name = config_file

    def get_config_path(self) -> str:
        # If config_name is already an absolute path from __init__, return it directly.
        # This handles the case where PushHandler(config_file="/full/path/to/push.ini") is passed.
        if os.path.isabs(self.config_name):
            return self.config_name

        file_path = self.config_path
        cfg_path = runtime_config.config_path
        if cfg_path:
            potential_dir = os.path.dirname(cfg_path)
            if os.path.isdir(potential_dir):
                file_path = potential_dir

        return os.path.join(file_path, self.config_name)

    def load_config(self) -> bool:
        file_path = self.get_config_path()
        if os.path.exists(file_path):
            try:
                self.cfg.read(file_path, encoding="utf-8")
                return True
            except Exception as e:
                log.warning(t("push.read_fail", error=e))
                return False
        return False

    # 推送消息中屏蔽关键词
    def msg_replace(self, msg: Any) -> str:
        block_keys = []
        try:
            # self.cfg is sync ConfigParser, checking if it was loaded
            # ConfigParser.get returns string
            block_str = self.cfg.get("setting", "push_block_keys")
            block_keys = block_str.split(",")
        except Exception:
            return str(msg)
        else:
            for block_key in block_keys:
                block_key_trim = str(block_key).strip()
                if block_key_trim:
                    msg = str(msg).replace(block_key_trim, "*" * len(block_key_trim))
            return str(msg)

    def _build_push_payload(
        self, status_id: int, push_message: str | None
    ) -> tuple[str, str, str]:
        """Build unified push payload for all channels."""
        title = get_push_title(status_id)
        content = str(push_message).strip() if push_message else ""
        if not content:
            content = t("push.empty_message")
        push_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = t("push.template_body", time=push_time, content=content)
        full_text = t("push.template_full", title=title, body=body)
        return title, body, full_text

    async def telegram(self, status_id: int, push_message: str | None) -> None:
        # Async telegram push
        _ = self.cfg.get("telegram", "http_proxy", fallback=None)
        # We need async get_new_session_use_proxy if we support proxy switch
        # For now let's assume global http supports proxy env vars or is configured

        # Or we can just use self.http.
        # get_new_session_use_proxy was sync.

        title, body, full_text = self._build_push_payload(status_id, push_message)
        # Simplified async version using global http
        url = f"https://{self.cfg.get('telegram', 'api_url')}/bot{self.cfg.get('telegram', 'bot_token')}/sendMessage"
        data = {
            "chat_id": self.cfg.get("telegram", "chat_id"),
            "text": full_text,
        }
        await self.http.post(url=url, data=data)

    async def ftqq(self, status_id: int, push_message: str | None) -> None:
        """
        Server酱推送，具体推送位置在server酱后台配置
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        await self.http.post(
            url="https://sctapi.ftqq.com/{}.send".format(
                self.cfg.get("setting", "push_token")
            ),
            data={"title": title, "desp": body},
        )

    async def pushplus(self, status_id: int, push_message: str | None) -> None:
        """
        PushPlus推送
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        await self.http.post(
            url="https://www.pushplus.plus/send",
            data={
                "token": self.cfg.get("setting", "push_token"),
                "title": title,
                "content": body,
                "topic": self.cfg.get("setting", "topic"),
            },
        )

    async def pushme(self, status_id: int, push_message: str | None) -> None:
        """
        PushMe推送
        """
        pushme_key = self.cfg.get("pushme", "token")
        if not pushme_key:
            log.error(t("push.pushme_key_missing"))
            return
        log.info(t("push.pushme_start"))
        title, body, _ = self._build_push_payload(status_id, push_message)
        data = {
            "push_key": pushme_key,
            "title": title,
            "content": body,
            "date": "",
            "type": "",
        }
        log.debug(f"PushMe 请求数据: {data}")
        response = await self.http.post(
            url=self.cfg.get("pushme", "url", fallback="https://push.i-i.me/"),
            data=data,
        )
        log.debug(f"PushMe 响应状态码: {response.status}")
        text = await response.text()
        log.debug(f"PushMe 响应内容: {text}")
        if response.status == 200 and text == "success":
            log.info(t("push.pushme_success"))
        else:
            log.error(t("push.pushme_fail", status=response.status, text=text))

    async def cqhttp(self, status_id: int, push_message: str | None) -> None:
        """
        OneBot V11(CqHttp)协议推送
        """
        qq = self.cfg.get("cqhttp", "cqhttp_qq", fallback=None)
        group = self.cfg.get("cqhttp", "cqhttp_group", fallback=None)

        if qq and group:
            log.error(t("push.cqhttp_config_err"))
            return

        _, _, full_text = self._build_push_payload(status_id, push_message)
        # use a flexible dict to allow numeric ids
        data: dict[str, Any] = {"message": full_text}
        if qq:
            data["user_id"] = int(qq)
        if group:
            data["group_id"] = int(group)

        await self.http.post(url=self.cfg.get("cqhttp", "cqhttp_url"), json=data)

    # 感谢 @islandwind 提供的随机壁纸api 个人主页：https://space.bilibili.com/7600422
    async def smtp(self, status_id: int, push_message: str | None) -> None:
        """
        SMTP 电子邮件推送
        """
        # SMTP is typically sync via smtplib. Running it in executor is better.
        import smtplib
        from email.mime.text import MIMEText

        title, body, _ = self._build_push_payload(status_id, push_message)

        async def get_background_url() -> str:
            try:
                resp = await self.http.get(
                    "https://api.iw233.cn/api.php?sort=random&type=json"
                )
                # resp.json() is untyped; cast result to expected structure
                data = await resp.json()
                return cast(str, data["pic"][0])
            except Exception:
                log.warning(t("push.smtp_img_fail"))
                return "unable to get the image"

        def get_background_img_html(background_url: str | None) -> str:
            if background_url:
                return f'<img src="{background_url}" alt="background" style="width: 100%; filter: brightness(50%)">'
            return ""

        def get_background_img_info(background_url: str | None) -> str:
            if background_url:
                return (
                    f'<p style="color: #fff;text-shadow:0px 0px 10px #000;">{t("push.smtp_img_title")}</p>\n'
                    f'<a href="{background_url}" style="color: #fff;text-shadow:0px 0px 10px #000;">{background_url}</a>'
                )
            return ""

        image_url = None
        if self.cfg.getboolean("smtp", "background", fallback=True):
            image_url = await get_background_url()

        def send_sync() -> None:
            try:
                with open("assets/email_example.html", encoding="utf-8") as f:
                    EMAIL_TEMPLATE = f.read()
            except FileNotFoundError:
                EMAIL_TEMPLATE = "{title}<br>{message}<br>{background_info}"

            message = EMAIL_TEMPLATE.format(
                title=title,
                message=body.replace("\n", "<br/>"),
                background_image=get_background_img_html(image_url),
                background_info=get_background_img_info(image_url),
            )
            smtp_info = self.cfg["smtp"]
            msg_mime = MIMEText(message, "html", "utf-8")
            msg_mime["Subject"] = smtp_info["subject"]
            msg_mime["To"] = smtp_info["toaddr"]
            msg_mime["From"] = f"{smtp_info['subject']}<{smtp_info['fromaddr']}>"

            # Annotate server as the base smtplib.SMTP to allow assignment of SMTP_SSL as well.
            server: smtplib.SMTP
            if self.cfg.getboolean("smtp", "ssl_enable"):
                server = smtplib.SMTP_SSL(
                    smtp_info["mailhost"], self.cfg.getint("smtp", "port")
                )
            else:
                server = smtplib.SMTP(
                    smtp_info["mailhost"], self.cfg.getint("smtp", "port")
                )
            server.login(smtp_info["username"], smtp_info["password"])
            server.sendmail(
                smtp_info["fromaddr"], smtp_info["toaddr"], msg_mime.as_string()
            )
            server.close()
            log.info(t("push.smtp_success"))

        await asyncio.to_thread(send_sync)

    async def wecom(self, status_id: int, push_message: str | None) -> None:
        """
        企业微信推送
        感谢linjie5493@github 提供的代码
        """
        secret = self.cfg.get("wecom", "secret")
        corpid = self.cfg.get("wecom", "wechat_id")
        try:
            touser = self.cfg.get("wecom", "touser")
        except NoOptionError:
            # 没有配置时赋默认值
            touser = "@all"

        _, _, full_text = self._build_push_payload(status_id, push_message)
        token_resp = await self.http.post(
            url=f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={secret}",
            data="",
        )
        push_token = (await token_resp.json())["access_token"]
        push_data = {
            "agentid": self.cfg.get("wecom", "agentid"),
            "msgtype": "text",
            "touser": touser,
            "text": {"content": full_text},
            "safe": 0,
        }
        await self.http.post(
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={push_token}",
            json=push_data,
        )

    async def wecomrobot(self, status_id: int, push_message: str | None) -> None:
        """
        企业微信机器人
        """
        _, _, full_text = self._build_push_payload(status_id, push_message)
        resp = await self.http.post(
            url=f"{self.cfg.get('wecomrobot', 'url')}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "msgtype": "text",
                "text": {
                    "content": full_text,
                    "mentioned_mobile_list": [
                        f"{self.cfg.get('wecomrobot', 'mobile')}"
                    ],
                },
            },
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("errmsg")))

    async def pushdeer(self, status_id: int, push_message: str | None) -> None:
        """
        PushDeer推送
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        await self.http.get(
            url=f"{self.cfg.get('pushdeer', 'api_url')}/message/push",
            params={
                "pushkey": self.cfg.get("pushdeer", "token"),
                "text": title,
                "desp": str(body).replace("\r\n", "\r\n\r\n"),
                "type": "markdown",
            },
        )

    async def dingrobot(self, status_id: int, push_message: str | None) -> None:
        """
        钉钉群机器人推送
        """
        _, _, full_text = self._build_push_payload(status_id, push_message)
        api_url = self.cfg.get(
            "dingrobot", "webhook"
        )  # https://oapi.dingtalk.com/robot/send?access_token=XXX
        secret = self.cfg.get("dingrobot", "secret")  # 安全设置 -> 加签 -> 密钥 -> SEC*
        if secret:
            timestamp = str(round(time.time() * 1000))
            sign_string = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                key=secret.encode("utf-8"),
                msg=sign_string.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = quote_plus(base64.b64encode(hmac_code))
            api_url = f"{api_url}&timestamp={timestamp}&sign={sign}"

        resp = await self.http.post(
            url=api_url,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"msgtype": "text", "text": {"content": full_text}},
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("errmsg")))

    async def feishubot(self, status_id: int, push_message: str | None) -> None:
        """
        飞书机器人(WebHook)
        """
        _, _, full_text = self._build_push_payload(status_id, push_message)
        api_url = self.cfg.get(
            "feishubot", "webhook"
        )  # https://open.feishu.cn/open-apis/bot/v2/hook/XXX
        resp = await self.http.post(
            url=api_url,
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"msg_type": "text", "content": {"text": full_text}},
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("msg")))

    async def bark(self, status_id: int, push_message: str | None) -> None:
        """
        Bark推送
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        # make send_title and push_message to url encode
        send_title = quote_plus(title)
        push_message = quote_plus(body)
        resp = await self.http.get(
            url=f"{self.cfg.get('bark', 'api_url')}/{self.cfg.get('bark', 'token')}/{send_title}/{push_message}?"
            f"icon=https://cdn.jsdelivr.net/gh/tanmx/pic@main/mihoyo/{self.cfg.get('bark', 'icon')}.png"
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("message")))

    async def gotify(self, status_id: int, push_message: str | None) -> None:
        """
        gotify
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        resp = await self.http.post(
            url=f"{self.cfg.get('gotify', 'api_url')}/message?token={self.cfg.get('gotify', 'token')}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "title": title,
                "message": body,
                "priority": self.cfg.getint("gotify", "priority"),
            },
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("errmsg")))

    async def ifttt(self, status_id: int, push_message: str | None) -> int:
        """
        ifttt
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        ifttt_event = self.cfg.get("ifttt", "event")
        ifttt_key = self.cfg.get("ifttt", "key")
        rep = await self.http.post(
            url=f"https://maker.ifttt.com/trigger/{ifttt_event}/with/key/{ifttt_key}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"value1": title, "value2": body},
        )
        text = await rep.text()
        if "errors" in text:
            # Note: The logic for parsing errors might need adjustment if json is returned
            try:
                log.warning(t("push.ifttt_err", error=(await rep.json())["errors"]))
            except Exception:
                log.warning(t("push.ifttt_err", error=text))
            return 0
        else:
            log.info(t("push.ifttt_done"))
        return 1

    async def webhook(self, status_id: int, push_message: str | None) -> None:
        """
        WebHook
        """
        title, body, _ = self._build_push_payload(status_id, push_message)
        resp = await self.http.post(
            url=f"{self.cfg.get('webhook', 'webhook_url')}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={"title": title, "message": body},
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep.get("errmsg")))

    async def qmsg(self, status_id: int, push_message: str | None) -> None:
        """
        qmsg
        """
        _, _, full_text = self._build_push_payload(status_id, push_message)
        resp = await self.http.post(
            url=f"https://qmsg.zendee.cn/send/{self.cfg.get('qmsg', 'key')}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"msg": full_text},
        )
        rep = await resp.json()
        log.info(t("push.result", result=rep["reason"]))

    async def discord(self, status_id: int, push_message: str | None) -> None:
        import pytz

        title, body, _ = self._build_push_payload(status_id, push_message)

        def get_color() -> int:
            embed_color = 16744192
            if status_id == 0:  # 成功
                embed_color = 1926125
            elif status_id == 1:  # 全部失败
                embed_color = 14368575
            elif status_id == 2 or status_id == 3:  # 部分失败
                embed_color = 16744192
            return embed_color

        rep = await self.http.post(
            url=f"{self.cfg.get('discord', 'webhook')}",
            headers={"Content-Type": "application/json; charset=utf-8"},
            json={
                "content": None,
                "embeds": [
                    {
                        "title": title,
                        "description": body,
                        "color": get_color(),
                        "author": {
                            "name": "MihoyoBBSTools",
                            "url": "https://github.com/Womsxd/MihoyoBBSTools",
                            "icon_url": "https://github.com/DGP-Studio/Snap.Hutao.Docs/blob/main/docs/.vuepress/public"
                            "/images/202308/hoyolab-miyoushe-Icon.png?raw=true ",
                        },
                        "timestamp": datetime.now(UTC)
                        .astimezone(pytz.timezone("Asia/Shanghai"))
                        .isoformat(),
                    }
                ],
                "username": "MihoyoBBSTools",
                "avatar_url": "https://github.com/DGP-Studio/Snap.Hutao.Docs/blob/main/docs/.vuepress/public/images"
                "/202308/hoyolab-miyoushe-Icon.png?raw=true",
                "attachments": [],
            },
        )
        if rep.status != 204:
            log.warning(t("push.discord_err", error=await rep.text()))
        else:
            log.info(t("push.discord_success", status=rep.status))

    def wintoast(self, status_id: int, push_message: str | None) -> None:
        try:
            toast = __import__("win11toast").toast
            title, body, _ = self._build_push_payload(status_id, push_message)

            # win11toast is often sync or creates its own loop. safe to call if it doesn't block too long.
            # But strictly it should be run in executor if it blocks.
            toast(app_id="MihoyoBBSTools", title=title, body=body, icon="")
        except Exception:
            log.error(t("push.wintoast_err"))

    async def serverchan3(self, status_id: int, push_message: str | None) -> None:
        title, body, _ = self._build_push_payload(status_id, push_message)
        sendkey = self.cfg.get("serverchan3", "sendkey")
        match = re.match(r"sctp(\d+)t", sendkey)
        if match:
            num = match.group(1)
            url = f"https://{num}.push.ft07.com/send/{sendkey}.send"
        else:
            raise ValueError(t("push.serverchan3_invalid_key"))
        data = {
            "title": title,
            "desp": body,
            "tags": self.cfg.get("serverchan3", "tags", fallback=""),
        }
        rep = await self.http.post(url=url, json=data)
        log.debug(await rep.text())

    # 其他推送方法，例如 ftqq, pushplus 等, 和 telegram 方法相似
    # 在类内部直接使用 self.cfg 读取配置

    async def push(self, status: int, push_message: str | None) -> int:
        if not self.load_config():
            return 1
        if not self.cfg.getboolean("setting", "enable"):
            return 0
        if (
            self.cfg.getboolean("setting", "error_push_only", fallback=False)
            and status == 0
        ):
            return 0
        log.info(t("push.execution_start"))
        func_names = self.cfg.get("setting", "push_server").lower()
        push_success = True
        for func_name in func_names.split(","):
            func = getattr(self, func_name, None)
            if not func:
                log.warning(t("push.server_err", name=func_name))
                continue
            log.debug(t("push.service_name", name=func_name))
            try:
                if inspect.iscoroutinefunction(func):
                    await func(status, self.msg_replace(push_message))
                else:
                    # Fallback for sync functions like wintoast
                    func(status, self.msg_replace(push_message))
            except Exception as e:
                log.warning(t("push.exec_fail", name=func_name, error=str(e)))
                push_success = False
                continue
            log.info(t("push.exec_done", name=func_name))
        return 0 if push_success else 1


async def async_push(
    status: int, push_message: str | None, config_path: str | None = None
) -> int:
    push_handler_instance = (
        PushHandler(config_file=config_path) if config_path else PushHandler()
    )
    return await push_handler_instance.push(status, push_message)


# Export async_push as push for callers using await
push = async_push

if __name__ == "__main__":
    asyncio.run(async_push(0, f"推送验证{int(time.time())}"))
