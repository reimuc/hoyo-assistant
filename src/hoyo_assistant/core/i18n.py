import json
import locale
import os
from typing import Any

from .loghelper import log


class I18n:
    def __init__(self):
        self._locales: dict[str, dict[str, Any]] = {}
        self._current_lang = "zh_CN"
        self._locales_dir = os.path.join(os.path.dirname(os.path.dirname(str(os.path.abspath(__file__)))), "locales")
        self._load_locales()
        self._detect_language()

    def _detect_language(self):
        """Detect system language or use ENVRIONMENT variable."""
        env_lang = os.getenv("HOYO_ASSISTANT_LANGUAGE")
        if env_lang:
            self._current_lang = env_lang
            log.debug(f"Language set from env: {self._current_lang}")
            return

        try:
            sys_lang_code = locale.getlocale()[0]
            if not sys_lang_code:
                lang_env = os.getenv("LANG", "")
                sys_lang_code = lang_env.split(".")[0].replace("-", "_") if lang_env else None
            if sys_lang_code:
                normalized_lang = sys_lang_code.replace("-", "_").lower()
                # Map system locale to our supported locales
                if normalized_lang.startswith("zh") or "chinese" in normalized_lang:
                    self._current_lang = "zh_CN"
                elif normalized_lang.startswith("en") or "english" in normalized_lang:
                    self._current_lang = "en_US"
                else:
                    self._current_lang = "en_US"  # Default fallback
                log.debug(f"Detected system language: {sys_lang_code}, using: {self._current_lang}")
        except Exception as e:
            log.warning(f"Failed to detect system language: {e}. Fallback to zh_CN.")
            self._current_lang = "zh_CN"

    def _load_locales(self):
        """Load all JSON files from locales directory."""
        if not os.path.exists(self._locales_dir):
            log.warning(f"Locales directory not found: {self._locales_dir}")
            return

        for filename in os.listdir(self._locales_dir):
            if filename.endswith(".json"):
                lang_code = filename[:-5]  # remove .json
                try:
                    with open(os.path.join(self._locales_dir, filename), encoding="utf-8") as f:
                        self._locales[lang_code] = json.load(f)
                    log.debug(f"Loaded locale: {lang_code}")
                except Exception as e:
                    log.error(f"Failed to load locale {filename}: {e}")

    def t(self, key: str, **kwargs) -> str:
        """
        Translate key (e.g. 'cli.task.single_start').
        Supports nested keys and format arguments.
        """
        keys = key.split(".")
        value = self._locales.get(self._current_lang, {})

        # Traverse
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break

        if value is None:
            return key

        if isinstance(value, str):
            if not kwargs:
                return value
            try:
                return value.format(**kwargs)
            except Exception as e:
                log.warning(f"Failed to format string '{value}' with args {kwargs}: {e}")
                return value

        return str(value)


# Singleton instance
i18n = I18n()

# Helper export
t = i18n.t
