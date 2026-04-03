import pytest

from hoyo_assistant.server import ServerSettings


def test_default_server_settings():
    s = ServerSettings()
    assert s.mode in ("single", "multi") or isinstance(s.mode, str)
    assert isinstance(s.interval, int)


def test_interval_setter_minimum():
    s = ServerSettings()
    s.interval = 10  # should be clamped to 60
    assert s.interval >= 60


def test_mode_setter_validation():
    s = ServerSettings()
    s.mode = "single"
    assert s.mode == "single"
    with pytest.raises(ValueError):
        s.mode = "invalid_mode"
