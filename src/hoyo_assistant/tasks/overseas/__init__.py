"""
Overseas server (HoYoLAB) tasks.
"""

from .cloud_games import run_task as run_cloud_task
from .game_signin import run_task as run_signin_task

__all__ = ["run_cloud_task", "run_signin_task"]
