import asyncio

from ...core import config
from ...core.i18n import t
from ...core.loghelper import log


async def run_task() -> None:
    """根据配置执行网页活动任务"""
    if not config.config.get("web_activity", {}).get("enable", False):
        log.info(t("web_activity.not_enabled"))
        return

    activities = config.config.get("web_activity", {}).get("activities", [])
    if not activities:
        log.info(t("web_activity.none_configured"))
        return

    log.info(f"{t('web_activity.start')} : {activities}")

    for activity in activities:
        try:
            # 检查是否有对应的函数
            func = globals().get(activity)
            if func and callable(func):
                log.info(t("web_activity.executing", name=activity))
                result = func()
                if asyncio.iscoroutine(result):
                    await result
                log.info(t("web_activity.done", name=activity))
            else:
                log.warning(t("web_activity.not_found", name=activity))
        except Exception as e:
            log.error(t("web_activity.error", name=activity, error=str(e)))
