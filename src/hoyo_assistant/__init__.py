"""
hoyo-assistant: A tool for automating HoYoLAB/MiYouShe daily tasks.
"""

from .runner import run_multi_account, run_single_account

__version__ = "1.0.0"
__all__ = ["run_multi_account", "run_single_account"]
