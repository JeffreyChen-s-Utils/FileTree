"""Translations: English, Traditional Chinese (Taiwan) and Simplified Chinese.

Every text the window shows goes through ``tr(key, **values)``. The string
tables live in ``je_file_tree.gui.strings``; a key missing from a language falls
back to English, and every language must define exactly the English keys
(``test_i18n`` checks this, and that the ``{placeholders}`` match).
"""

from __future__ import annotations

from je_file_tree.gui.strings import STRINGS

LANGUAGES: dict[str, str] = {"en": "English", "zh-TW": "繁體中文", "zh-CN": "简体中文"}
DEFAULT_LANGUAGE = "en"
_state = {"language": DEFAULT_LANGUAGE}
_SECONDS_PER_MINUTE = 60
_WHOLE_SECONDS_FROM = 10


def set_language(code: str) -> None:
    """Use ``code`` (a key of ``LANGUAGES``) for every text from now on."""
    if code not in LANGUAGES:
        raise ValueError(f"unknown language: {code!r}")
    _state["language"] = code


def current_language() -> str:
    """The language in use."""
    return _state["language"]


def tr(key: str, **values: object) -> str:
    """The text for ``key`` in the current language, with ``{placeholders}`` filled from ``values``."""
    text = STRINGS[_state["language"]].get(key)
    if text is None:
        text = STRINGS[DEFAULT_LANGUAGE][key]
    return text.format(**values) if values else text


def match_language(locale_name: str) -> str:
    """The supported language closest to a system locale name such as ``"zh_TW"`` or ``"en_US"``."""
    name = locale_name.replace("-", "_").lower()
    if not name.startswith("zh"):
        return DEFAULT_LANGUAGE
    traditional = ("_tw", "_hk", "_mo", "hant")
    return "zh-TW" if any(marker in name for marker in traditional) else "zh-CN"


def format_duration(seconds: float) -> str:
    """A duration as short text in the current language, e.g. ``"0.8 s"`` or ``"3 min 5 s"``."""
    if seconds < _WHOLE_SECONDS_FROM:
        return tr("duration_seconds", value=f"{seconds:.1f}")
    whole = round(seconds)
    if whole < _SECONDS_PER_MINUTE:
        return tr("duration_seconds", value=str(whole))
    minutes, rest = divmod(whole, _SECONDS_PER_MINUTE)
    return tr("duration_minutes", minutes=minutes, seconds=rest)
