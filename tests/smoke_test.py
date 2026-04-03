"""Lightweight smoke test for import and entry compatibility."""

# ruff: noqa: E402

import sys
from pathlib import Path

# Add src to sys.path to simulate package installation or dev environment
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(PROJECT_ROOT) not in sys.path:
    # Need to add project root to path to import main.py, main_multi.py, index.py
    sys.path.insert(0, str(PROJECT_ROOT))

# Import setting from package after ensuring src is on sys.path
# Import from package
# Import root modules
from hoyo_assistant.core import request, setting
from hoyo_assistant.core.constants import StatusCode
from hoyo_assistant.runner import multi_account, single_account
from hoyo_assistant.tasks.chinese import (
    cloud_games as cn_cloud_games,
    game_signin as cn_game_signin,
)
from hoyo_assistant.tasks.overseas import (
    cloud_games as os_cloud_games,
    game_signin as os_game_signin,
)


def run() -> int:
    print("Starting smoke test...")
    assert StatusCode.SUCCESS.value == 0

    # Check runner functions
    assert callable(single_account.run_once)
    assert callable(single_account.run_single_account)
    assert callable(multi_account.run_multi_account)

    # Check task modules have run_task
    assert callable(cn_game_signin.run_task)
    assert callable(cn_cloud_games.run_task)
    assert callable(os_game_signin.run_task)
    assert callable(os_cloud_games.run_task)

    print("Imports successful.")

    # Check main entry points
    assert hasattr(setting, "load_config")
    assert hasattr(request, "http")

    # Check OS cloud games setting
    # assert hasattr(setting, "cloud_genshin_sign_os")
    # assert hasattr(setting, "cloud_zzz_sign_os")

    print("Smoke test passed!")
    return 0


if __name__ == "__main__":
    sys.exit(run())
