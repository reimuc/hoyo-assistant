from dataclasses import dataclass, field
from threading import Event


@dataclass
class CloudGameInfo:
    name: str
    api: str
    biz: str
    hostname: str | None = None


@dataclass
class ServerSettings:
    """Server runtime settings / state.

    Use public attributes for state and provide small properties for controlled access.
    """

    # backing field for mode (keep private to allow validation in property)
    _mode: str = "multi"

    # public configuration fields
    config_path: str | list[str] | None = None
    push_config_path: str | None = None

    # interval stored in seconds
    _interval: int = 720 * 60  # 12 hours

    use_env: bool = False

    # runtime state
    next_run: float = 0.0
    last_run: float = 0.0
    running: bool = False
    stop_event: Event = field(default_factory=Event)

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in ("single", "multi"):
            raise ValueError("mode must be 'single' or 'multi'")
        self._mode = value

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, seconds: int) -> None:
        self._interval = max(60, seconds)
