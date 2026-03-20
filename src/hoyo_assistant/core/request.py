import asyncio
from typing import Any, Optional

import aiohttp
import orjson
from aiohttp import ClientResponse
from cachetools import TTLCache
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .constants import (
    ASYNC_TIMEOUT,
    CACHE_MAX_SIZE,
    CACHE_TTL,
    CONNECTOR_LIMIT,
    CONNECTOR_LIMIT_PER_HOST,
    DEFAULT_HEADERS,
    DNS_SERVERS,
    RETRY_INTERVAL,
    RETRY_TIMES,
)
from .i18n import t
from .loghelper import log


class MockResponse:
    """模拟 aiohttp.ClientResponse 用于缓存返回"""

    def __init__(self, data: Any, status: int = 200, url: str = ""):
        self._data = data
        self._body = None
        self.url = url
        self.status = status
        self.headers = {}

    async def json(self, **kwargs):
        return self._data

    async def text(self, **kwargs):
        if self._body is None:
            try:
                self._body = orjson.dumps(self._data).decode()
            except Exception:
                self._body = str(self._data)
        return self._body

    async def read(self):
        text = await self.text()
        return text.encode("utf-8")

    def raise_for_status(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def release(self):
        pass


class HttpClient:
    """异步API客户端，支持连接池、缓存和智能重试"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: TTLCache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)
        self.request_count = 0
        self.cache_hits = 0

    @staticmethod
    def _freeze(value: Any) -> Any:
        """Convert nested request args into a hashable canonical form."""
        if isinstance(value, dict):
            return tuple(sorted((str(k), HttpClient._freeze(v)) for k, v in value.items()))
        if isinstance(value, (list, tuple, set)):
            return tuple(HttpClient._freeze(v) for v in value)
        return value

    def _build_cache_key(self, url: str, **kwargs) -> tuple:
        params = kwargs.get("params") or {}
        headers = kwargs.get("headers") or {}
        auth_scope = {
            "cookie": headers.get("cookie") or headers.get("Cookie") or "",
            "authorization": headers.get("authorization") or headers.get("Authorization") or "",
        }
        return url, self._freeze(params), self._freeze(auth_scope)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def initialize(self):
        """初始化会话和连接池"""
        if self.session and not self.session.closed:
            return

        resolver = None
        try:
            resolver = aiohttp.AsyncResolver(nameservers=DNS_SERVERS)
        except Exception:
            log.warning(t("system.dns_fail"))

        connector = aiohttp.TCPConnector(
            limit=CONNECTOR_LIMIT,
            limit_per_host=CONNECTOR_LIMIT_PER_HOST,
            ttl_dns_cache=300,
            resolver=resolver,
        )
        timeout = aiohttp.ClientTimeout(total=ASYNC_TIMEOUT)

        # Use simple lambda for json serialization if needed
        json_serializer = lambda x: orjson.dumps(x).decode()

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=DEFAULT_HEADERS,
            json_serialize=json_serializer,
            trust_env=True,
        )
        log.debug(t("system.client_init"))

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            log.debug(t("system.client_close"))

        rate = self.cache_hits / max(self.request_count, 1) * 100
        log.info(t("system.client_stats", count=self.request_count, hits=self.cache_hits, rate=f"{rate:.1f}"))

    async def request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> None | MockResponse | ClientResponse:  # Returns aiohttp.ClientResponse or MockResponse
        """发送HTTP请求，支持缓存和重试"""
        self.request_count += 1
        use_cache = kwargs.pop("use_cache", True)
        cache_key = None

        # 检查缓存（仅GET请求）
        if method.upper() == "GET" and use_cache:
            cache_key = self._build_cache_key(url, **kwargs)
        if cache_key is not None and cache_key in self.cache:
            self.cache_hits += 1
            log.debug(t("system.cache_hit", url=url))
            return MockResponse(self.cache[cache_key], url=url)

        if not self.session or self.session.closed:
            await self.initialize()

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
                stop=stop_after_attempt(RETRY_TIMES),
                wait=wait_exponential(multiplier=RETRY_INTERVAL, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    response = await self.session.request(method, url, **kwargs)

                    try:
                        await response.read()

                        if response.status == 200 and cache_key is not None:
                            try:
                                # Try parse JSON for caching
                                if "application/json" in response.headers.get("Content-Type", "").lower():
                                    data = await response.json()
                                    self.cache[cache_key] = data
                            except:
                                pass

                        if response.status == 429:  # Rate limit
                            reset_time = response.headers.get("X-RateLimit-Reset")
                            log.warning(t("system.rate_limit", reset_time=reset_time))
                            # Raise so retry works
                            raise aiohttp.ClientError("Rate limited")

                        return response

                    except Exception as e:
                        response.release()
                        log.debug(t("system.request_success"), result=e)
                        raise e

        except RetryError as e:
            log.error(t("system.retry_fail", retry=RETRY_TIMES, url=url))
            raise e
        except Exception as e:
            log.error(t("system.request_exception", error=str(e)))
            raise e

    async def get(self, url: str, **kwargs) -> None | MockResponse | ClientResponse:
        """发送GET请求"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> None | MockResponse | ClientResponse:
        """发送POST请求"""
        return await self.request("POST", url, **kwargs)

    async def raw_get(self, url: str) -> Optional[bytes]:
        """获取原始二进制内容（用于下载文件）"""
        self.request_count += 1

        if not self.session:
            await self.initialize()

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
                stop=stop_after_attempt(RETRY_TIMES),
                wait=wait_exponential(multiplier=RETRY_INTERVAL, min=1, max=10),
                reraise=True,
            ):
                with attempt:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            return await response.read()
                        else:
                            raise aiohttp.ClientError(f"HTTP {response.status}")

        except RetryError:
            log.error(t("system.retry_fail", retry=RETRY_TIMES, url=url))
            return None
        except Exception as e:
            log.error(t("system.request_exception", error=str(e)))
            return None

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        log.debug(t("system.cache_cleared"))

    def clear_cookies(self):
        """清空会话Cookie"""
        if self.session:
            self.session.cookie_jar.clear()
        log.debug(t("system.cookies_cleared"))


# Export global instance
http = HttpClient()
