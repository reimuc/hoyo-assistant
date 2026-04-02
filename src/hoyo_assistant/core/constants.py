from enum import IntEnum
from typing import Final

# =============================================================================
# Functional Constants (System & Network)
# =============================================================================
ASYNC_TIMEOUT: Final[int] = 30
RETRY_TIMES: Final[int] = 3
RETRY_INTERVAL: Final[float] = 1.0
MAX_WORKERS: Final[int] = 5

# Cache
CACHE_MAX_SIZE: Final[int] = 100
CACHE_TTL: Final[int] = 300  # 5 minutes

# Connection Pool
CONNECTOR_LIMIT: Final[int] = 100
CONNECTOR_LIMIT_PER_HOST: Final[int] = 20

# DNS
DNS_SERVERS: Final[list[str]] = [
    "223.5.5.5",  # AliDNS
    "119.29.29.29",  # DNSPod
    "8.8.8.8",  # Google
    "1.1.1.1",  # Cloudflare
]


# =============================================================================
# Status Constants (Enum)
# =============================================================================
class StatusCode(IntEnum):
    """Shared task status contract across run and push modules."""

    SUCCESS = 0
    FAILURE = 1
    PARTIAL_FAILURE = 2
    CAPTCHA_TRIGGERED = 3


# =============================================================================
# Business Constants (Game & BBS Logic)
# =============================================================================
# Salt
MIHOYOBBS_SALT: Final[str] = "b0EofkfMKq2saWV9fwux18J5vzcFTlex"
MIHOYOBBS_SALT_WEB: Final[str] = "DlOUwIupfU6YespEUWDJmXtutuXV6owG"
MIHOYOBBS_SALT_X4: Final[str] = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"
MIHOYOBBS_SALT_X6: Final[str] = "t0qEgfub6cvueAPgR5m9aQWWVciEer7v"

MIHOYOBBS_VERIFY_KEY: Final[str] = "bll8iq97cem8"
MIHOYOBBS_VERSION: Final[str] = "2.99.1"

# Client Type
MIHOYOBBS_CLIENT_TYPE: Final[str] = "2"  # 1: ios, 2: android
MIHOYOBBS_CLIENT_TYPE_WEB: Final[str] = "5"  # 4: pc web, 5: mobile web

# Post Types
MIHOYOBBS_POST_TYPES: Final[dict[int, dict[str, str]]] = {
    1: {"id": "1", "forumId": "1", "name": "崩坏3"},
    2: {"id": "2", "forumId": "26", "name": "原神"},
    3: {"id": "3", "forumId": "30", "name": "崩坏2"},
    4: {"id": "4", "forumId": "37", "name": "未定事件簿"},
    5: {"id": "5", "forumId": "34", "name": "大别野"},
    6: {"id": "6", "forumId": "52", "name": "崩坏：星穹铁道"},
    8: {"id": "8", "forumId": "57", "name": "绝区零"},
    9: {"id": "9", "forumId": "948", "name": "崩坏：因缘精灵"},
    10: {"id": "10", "forumId": "950", "name": "星布谷地"},
}

# Game Info
GAME_INFO_ID_TO_NAME: Final[dict[str, str]] = {
    "bh2_cn": "崩坏2",
    "bh3_cn": "崩坏3",
    "nxx_cn": "未定事件簿",
    "hk4e_cn": "原神",
    "hkrpg_cn": "崩坏：星穹铁道",
    "nap_cn": "绝区零",
    "abc_cn": "崩坏：因缘精灵",
}

GAME_INFO_ID_TO_CONFIG: Final[dict[str, str]] = {
    "bh2_cn": "honkai2",
    "bh3_cn": "honkai3rd",
    "nxx_cn": "tears_of_themis",
    "hk4e_cn": "genshin",
    "hkrpg_cn": "honkaisr",
    "nap_cn": "zzz",
    "abc_cn": "hna",
}

# Values for Headers Template (used below)
_UA_TEMPLATE = (
    "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36 miHoYoBBS/{MIHOYOBBS_VERSION}"
)

# Headers Template
DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "DS": "",
    "x-rpc-channel": "miyousheluodi",
    "Origin": "https://webstatic.mihoyo.com",
    "x-rpc-app_version": MIHOYOBBS_VERSION,
    "User-Agent": _UA_TEMPLATE,
    "x-rpc-client_type": MIHOYOBBS_CLIENT_TYPE_WEB,
    "Referer": "",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,en-US;q=0.8",
    "X-Requested-With": "com.mihoyo.hyperion",
    "Cookie": "",
    "x-rpc-device_id": "",
}

# API Constants
# Base URLs
API_BBS: Final[str] = "https://bbs-api.miyoushe.com"
API_WEB: Final[str] = "https://api-takumi.mihoyo.com"
API_PASSPORT: Final[str] = "https://passport-api.mihoyo.com"
API_HK4E: Final[str] = "https://hk4e-api.mihoyo.com"
API_CLOUD_GENSHIN: Final[str] = "https://api-cloudgame.mihoyo.com"
API_CLOUD_ZZZ: Final[str] = "https://cg-nap-api.mihoyo.com"
API_ZZZ_WEB: Final[str] = "https://act-nap-api.mihoyo.com"

# OS URLs
API_CLOUD_GENSHIN_OS: Final[str] = "https://sg-cg-api.hoyoverse.com"
API_OS_REFERER: Final[str] = "https://act.hoyolab.com/"

# User & Token APIs
API_ACCOUNT_INFO: Final[str] = f"{API_WEB}/binding/api/getUserGameRolesByCookie"
API_GET_TOKEN_BY_STOKEN: Final[str] = (
    f"{API_PASSPORT}/account/ma-cn-session/app/getTokenBySToken"
)
API_BBS_ACCOUNT_INFO: Final[str] = (
    "https://webapi.account.mihoyo.com/Api/cookie_accountinfo_by_loginticket"
)
API_BBS_GET_MULTI_TOKEN: Final[str] = f"{API_WEB}/auth/api/getMultiTokenByLoginTicket"
API_BBS_GET_COOKIE_TOKEN: Final[str] = (
    f"{API_WEB}/auth/api/getCookieAccountInfoBySToken"
)

# BBS Tasks & Posts
API_BBS_TASKS_LIST: Final[str] = f"{API_BBS}/apihub/wapi/getUserMissionsState"
API_BBS_SIGN: Final[str] = f"{API_BBS}/apihub/app/api/signIn"
API_BBS_POST_LIST: Final[str] = f"{API_BBS}/post/api/getForumPostList"
API_BBS_POST_DETAIL: Final[str] = f"{API_BBS}/post/api/getPostFull"
API_BBS_SHARE: Final[str] = f"{API_BBS}/apihub/api/getShareConf"
API_BBS_LIKE: Final[str] = f"{API_BBS}/apihub/sapi/upvotePost"
API_BBS_GET_CAPTCHA: Final[str] = f"{API_BBS}/misc/api/createVerification?is_high=true"
API_BBS_CAPTCHA_VERIFY: Final[str] = f"{API_BBS}/misc/api/verifyVerification"

# Game Check-in
CN_GAME_LANG: Final[str] = "zh-cn"
API_CN_GAME_CHECKIN_REWARDS: Final[str] = (
    f"{API_WEB}/event/luna/home?lang={CN_GAME_LANG}"
)
API_CN_GAME_IS_SIGN: Final[str] = f"{API_WEB}/event/luna/info?lang={CN_GAME_LANG}"
API_CN_GAME_SIGN: Final[str] = f"{API_WEB}/event/luna/sign"

# Cloud Games - CN
API_CLOUD_GENSHIN_SIGN: Final[str] = f"{API_CLOUD_GENSHIN}/hk4e_cg_cn/wallet/wallet/get"
API_CLOUD_ZZZ_SIGN: Final[str] = f"{API_CLOUD_ZZZ}/nap_cn/cg/wallet/wallet/get"

# Cloud Games - OS
API_CLOUD_GENSHIN_SIGN_OS: Final[str] = (
    f"{API_CLOUD_GENSHIN_OS}/hk4e_global/cg/wallet/wallet/get"
)
API_CLOUD_ZZZ_SIGN_OS: Final[str] = (
    f"{API_CLOUD_GENSHIN_OS}/nap_global/cg/wallet/wallet/get"
)

# HK4E / Genius Invokation
API_HK4E_TOKEN_GET_INFO: Final[str] = f"{API_WEB}/common/badge/v1/login/info"
API_GET_HK4E_TOKEN: Final[str] = f"{API_WEB}/common/badge/v1/login/account"
API_GENIUS_INVOKATION_STATUS: Final[str] = (
    f"{API_HK4E}/event/geniusinvokationtcg/rd_info"
)
API_GENIUS_INVOKATION_TASK_LIST: Final[str] = (
    f"{API_HK4E}/event/geniusinvokationtcg/adventure_task_list"
)
API_GENIUS_INVOKATION_GET_AWARD: Final[str] = (
    f"{API_HK4E}/event/geniusinvokationtcg/award_adventure_task"
)
API_GENIUS_INVOKATION_FINISH_TASK: Final[str] = (
    f"{API_HK4E}/event/geniusinvokationtcg/finish_adventure_task"
)

# ZZZ Check-in
API_ZZZ_GAME_CHECKIN_REWARDS: Final[str] = (
    f"{API_ZZZ_WEB}/event/luna/zzz/home?lang={CN_GAME_LANG}"
)
API_ZZZ_GAME_IS_SIGN: Final[str] = (
    f"{API_ZZZ_WEB}/event/luna/zzz/info?lang={CN_GAME_LANG}"
)
API_ZZZ_GAME_SIGN: Final[str] = f"{API_ZZZ_WEB}/event/luna/zzz/sign"

# CN Game Signin Referers (Base)
REF_BH2_SIGN: Final[str] = (
    "https://webstatic.mihoyo.com/bbs/event/signin/bh2/index.html"
)
REF_BH3_SIGN: Final[str] = (
    "https://webstatic.mihoyo.com/bbs/event/signin/bh3/index.html"
)
REF_NXX_SIGN: Final[str] = (
    "https://webstatic.mihoyo.com/bbs/event/signin/nxx/index.html"
)
REF_GENSHIN_SIGN: Final[str] = (
    "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html"
)

# OS Game Signin Base URL
API_OS_ACT: Final[str] = "https://sg-hk4e-api.hoyolab.com/event/sol"
API_OS_ACT_HSR: Final[str] = "https://sg-public-api.hoyolab.com/event/luna/os"
API_OS_ACT_HI3: Final[str] = "https://sg-public-api.hoyolab.com/event/mani"
API_OS_ACT_ZZZ: Final[str] = "https://sg-act-nap-api.hoyolab.com/event/luna/zzz/os"

# Activity IDs (Flattened)
# CN
ACT_ID_CN_HONKAI2: Final[str] = "e202203291431091"
ACT_ID_CN_HONKAI3RD: Final[str] = "e202306201626331"
ACT_ID_CN_TEARS_OF_THEMIS: Final[str] = "e202202251749321"
ACT_ID_CN_GENSHIN: Final[str] = "e202311201442471"
ACT_ID_CN_HONKAI_SR: Final[str] = "e202304121516551"
ACT_ID_CN_ZZZ: Final[str] = "e202406242138391"

# OS
ACT_ID_OS_GENSHIN: Final[str] = "e202102251931481"
ACT_ID_OS_HONKAI3RD: Final[str] = "e202110291205111"
ACT_ID_OS_TEARS_OF_THEMIS: Final[str] = "e202202281857121"
ACT_ID_OS_HONKAI_SR: Final[str] = "e202303301540311"
ACT_ID_OS_ZZZ: Final[str] = "e202406031448091"
