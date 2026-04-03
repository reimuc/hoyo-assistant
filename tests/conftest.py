import sys
import types

# Provide a minimal stub for aiohttp to avoid importing the real package during tests
# which may pull in heavy dependencies (yarl/pydantic) and cause environment issues.
aiohttp_stub = types.ModuleType("aiohttp")


class ClientError(Exception):
    pass


class AsyncResolver:
    def __init__(self, *args, **kwargs):
        pass


class TCPConnector:
    def __init__(self, *args, **kwargs):
        pass


class ClientTimeout:
    def __init__(self, *args, **kwargs):
        pass


class ClientSession:
    def __init__(self, *args, **kwargs):
        # emulate closed attribute used by HttpClient
        self.closed = True
        self.cookie_jar = types.SimpleNamespace()

    async def close(self):
        self.closed = True

    async def request(self, *args, **kwargs):
        # simple async context compatible stub
        class _Resp:
            status = 200
            headers = {}

            async def read(self):
                return b""

            async def json(self):
                return {}

            def release(self):
                pass

        return _Resp()


# attach to module
aiohttp_stub.ClientError = ClientError
aiohttp_stub.AsyncResolver = AsyncResolver
aiohttp_stub.TCPConnector = TCPConnector
aiohttp_stub.ClientTimeout = ClientTimeout
aiohttp_stub.ClientSession = ClientSession

# insert into sys.modules early so imports in package pick up this stub
sys.modules.setdefault("aiohttp", aiohttp_stub)

# Minimal stub for pydantic to avoid pydantic-core runtime mismatch in test env
pydantic_stub = types.ModuleType("pydantic")


class _BaseModel:
    pass


def _BeforeValidator(fn):
    return fn


def _Field(*args, **kwargs):
    # Return a sentinel object; actual value isn't needed for import-time
    return kwargs.get("default")


pydantic_stub.BaseModel = _BaseModel
pydantic_stub.BeforeValidator = _BeforeValidator
pydantic_stub.Field = _Field

sys.modules.setdefault("pydantic", pydantic_stub)

# Minimal stub for pydantic_settings
pydantic_settings_stub = types.ModuleType("pydantic_settings")


class _BaseSettings:
    def __init__(self, *args, **kwargs):
        # accept arbitrary init args, do nothing
        super().__init__()

    def model_dump(self) -> dict:
        # provide minimal dump expected by code under test
        return {}


# used in annotations only; provide simple placeholders
pydantic_settings_stub.BaseSettings = _BaseSettings
pydantic_settings_stub.PydanticBaseSettingsSource = object
pydantic_settings_stub.SettingsConfigDict = dict

sys.modules.setdefault("pydantic_settings", pydantic_settings_stub)
