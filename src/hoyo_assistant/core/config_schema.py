from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class BaseConfigModel(BaseModel):
    model_config = {"extra": "ignore"}


def coerce_to_str(v: Any) -> str:
    return str(v)


CoercedStr = Annotated[str, BeforeValidator(coerce_to_str)]


class AccountConfig(BaseConfigModel):
    cookie: str = Field("", description="MiHoYo BBS Cookie")
    stuid: CoercedStr = Field("", description="Account STUID")
    stoken: str = Field("", description="Account SToken")
    mid: CoercedStr = Field("", description="Account MID")


class DeviceConfig(BaseConfigModel):
    name: str = "Xiaomi MI 6"
    model: str = "Mi 6"
    id: str = ""
    fp: str = ""


class MihoyoBBSConfig(BaseConfigModel):
    enable: bool = True
    checkin: bool = True
    checkin_list: list[int] = Field(
        default_factory=lambda: [5, 2], description="Forum IDs to checkin"
    )
    read: bool = True
    like: bool = True
    cancel_like: bool = True
    share: bool = True


class GameItemConfig(BaseConfigModel):
    checkin: bool = False
    black_list: list[str] = Field(
        default_factory=list, description="List of blacklisted account IDs"
    )


class BaseGamesConfig(BaseConfigModel):
    genshin: GameItemConfig = Field(default_factory=GameItemConfig)
    honkai2: GameItemConfig = Field(default_factory=GameItemConfig)
    honkai3rd: GameItemConfig = Field(default_factory=GameItemConfig)
    tears_of_themis: GameItemConfig = Field(default_factory=GameItemConfig)
    honkai_sr: GameItemConfig = Field(default_factory=GameItemConfig)
    zzz: GameItemConfig = Field(default_factory=GameItemConfig)


class GamesCNConfig(BaseGamesConfig):
    enable: bool = True
    useragent: str = (
        "Mozilla/5.0 (Linux; Android 12; Unspecified Device) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Version/4.0 Chrome/103.0.5060.129 Mobile Safari/537.36"
    )
    retries: int = 3
    # Override defaults where needed
    genshin: GameItemConfig = Field(
        default_factory=lambda: GameItemConfig(checkin=True)
    )


class GamesOSConfig(BaseGamesConfig):
    enable: bool = False
    cookie: str = ""
    lang: str = "zh-cn"
    # OS games typically exclude Honkai 2 (Gun Girl Z) if not supported or maintained separately
    # But inheriting covers it harmlessly if unused.
    pass


class GamesConfig(BaseConfigModel):
    cn: GamesCNConfig = Field(default_factory=GamesCNConfig)
    os: GamesOSConfig = Field(default_factory=GamesOSConfig)


class CloudGameItemConfig(BaseConfigModel):
    enable: bool = False
    token: str = ""


class CloudGamesCNConfig(BaseConfigModel):
    enable: bool = False
    genshin: CloudGameItemConfig = Field(default_factory=CloudGameItemConfig)
    zzz: CloudGameItemConfig = Field(default_factory=CloudGameItemConfig)


class CloudGamesOSConfig(BaseConfigModel):
    enable: bool = False
    lang: str = "zh-cn"
    genshin: CloudGameItemConfig = Field(default_factory=CloudGameItemConfig)
    zzz: CloudGameItemConfig = Field(default_factory=CloudGameItemConfig)


class CloudGamesConfig(BaseConfigModel):
    cn: CloudGamesCNConfig = Field(default_factory=CloudGamesCNConfig)
    os: CloudGamesOSConfig = Field(default_factory=CloudGamesOSConfig)


class GeniusInvokationConfig(BaseConfigModel):
    enable: bool = False
    account: list[str] = Field(default_factory=list)
    checkin: bool = False
    weekly: bool = False


class CompetitionConfig(BaseConfigModel):
    enable: bool = False
    genius_invokation: GeniusInvokationConfig = Field(
        default_factory=GeniusInvokationConfig
    )


class WebActivityConfig(BaseConfigModel):
    enable: bool = False
    activities: list[str] = Field(default_factory=list)


class HoyoSettings(BaseSettings):
    enable: bool = True
    version: int = 15
    push: str = ""
    account: AccountConfig = Field(default_factory=AccountConfig)
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    mihoyobbs: MihoyoBBSConfig = Field(default_factory=MihoyoBBSConfig)
    games: GamesConfig = Field(default_factory=GamesConfig)
    cloud_games: CloudGamesConfig = Field(default_factory=CloudGamesConfig)
    competition: CompetitionConfig = Field(default_factory=CompetitionConfig)
    web_activity: WebActivityConfig = Field(default_factory=WebActivityConfig)

    model_config = SettingsConfigDict(
        env_prefix="HOYO_ASSISTANT_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: Env > Init (YAML/Kwargs) > DotEnv > Secrets
        return (
            env_settings,
            init_settings,
            dotenv_settings,
            file_secret_settings,
        )
