"""Translations: complete, consistent, and in the right variety of Chinese."""

from __future__ import annotations

import re
import string

import pytest

from file_tree.core.analysis import CATEGORIES
from file_tree.gui import i18n
from file_tree.gui.strings import STRINGS

_PLACEHOLDER = string.Formatter()


def _placeholders(text: str) -> set[str]:
    return {field for _, field, _, _ in _PLACEHOLDER.parse(text) if field}


@pytest.fixture(autouse=True)
def _english_afterwards():
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def test_every_language_has_exactly_the_english_keys() -> None:
    assert set(STRINGS) == set(i18n.LANGUAGES)
    english = set(STRINGS["en"])
    for language, table in STRINGS.items():
        assert set(table) == english, language


@pytest.mark.parametrize("language", ["zh-TW", "zh-CN"])
def test_placeholders_match_english(language: str) -> None:
    for key, text in STRINGS["en"].items():
        assert _placeholders(STRINGS[language][key]) == _placeholders(text), key


def test_every_file_type_group_has_a_name() -> None:
    for category in CATEGORIES:
        assert f"category_{category}" in STRINGS["en"]


def test_tr_fills_placeholders_in_the_current_language() -> None:
    assert i18n.tr("welcome_drive_tip", path="C:\\") == "Scan C:\\"
    i18n.set_language("zh-TW")
    assert i18n.tr("welcome_drive_tip", path="C:\\") == "掃描 C:\\"
    assert i18n.current_language() == "zh-TW"


def test_an_unknown_language_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown language"):
        i18n.set_language("xx")


@pytest.mark.parametrize(("locale_name", "language"), [
    ("en_US", "en"), ("de_DE", "en"), ("zh_TW", "zh-TW"), ("zh_HK", "zh-TW"),
    ("zh-Hant-TW", "zh-TW"), ("zh_CN", "zh-CN"), ("zh_SG", "zh-CN"), ("C", "en"),
])
def test_match_language(locale_name: str, language: str) -> None:
    assert i18n.match_language(locale_name) == language


def test_format_duration() -> None:
    assert i18n.format_duration(0.84) == "0.8 s"
    assert i18n.format_duration(42.4) == "42 s"
    assert i18n.format_duration(185) == "3 min 5 s"
    i18n.set_language("zh-TW")
    assert i18n.format_duration(185) == "3 分 5 秒"


# Words that give away Mainland usage in Taiwanese text, and the reverse.
_MAINLAND_WORDS = ("文件夾", "設置", "默認", "視頻", "軟件", "信息", "網絡", "用戶", "點擊", "數據", "緩存", "屏幕",
                   "鏈接", "菜單", "程序")
_TAIWAN_ONLY_CHARACTERS = "檔資夾設預視軟體訊網點擊選擇"


def test_traditional_chinese_uses_taiwanese_words() -> None:
    for key, text in STRINGS["zh-TW"].items():
        for word in _MAINLAND_WORDS:
            assert word not in text, f"{key}: {word}"


def test_simplified_chinese_uses_simplified_characters() -> None:
    pattern = re.compile(f"[{_TAIWAN_ONLY_CHARACTERS}]")
    for key, text in STRINGS["zh-CN"].items():
        assert not pattern.search(text), f"{key}: {pattern.findall(text)}"
