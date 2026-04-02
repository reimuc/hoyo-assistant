from dataclasses import dataclass


@dataclass
class CloudGameInfo:
    name: str
    api: str
    biz: str
    hostname: str | None = None
