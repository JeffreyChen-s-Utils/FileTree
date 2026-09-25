"""The translated READMEs follow the English one: same sections, same commands, same pictures."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_ENGLISH = _ROOT / "README.md"
_TRANSLATIONS = sorted((_ROOT / "README").glob("README_*.md"))
_CODE_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _heading_levels(text: str) -> list[int]:
    without_code = _CODE_BLOCK.sub("", text)
    return [len(match.group(1)) for match in re.finditer(r"^(#{1,6}) ", without_code, re.MULTILINE)]


def _table_rows(text: str) -> int:
    return len(re.findall(r"^\|", _CODE_BLOCK.sub("", text), re.MULTILINE))


def test_every_language_is_there() -> None:
    assert [path.name for path in _TRANSLATIONS] == ["README_zh-CN.md", "README_zh-TW.md"]


@pytest.mark.parametrize("translation", _TRANSLATIONS, ids=lambda path: path.name)
def test_same_sections(translation: Path) -> None:
    assert _heading_levels(_read(translation)) == _heading_levels(_read(_ENGLISH))


@pytest.mark.parametrize("translation", _TRANSLATIONS, ids=lambda path: path.name)
def test_same_commands(translation: Path) -> None:
    assert _CODE_BLOCK.findall(_read(translation)) == _CODE_BLOCK.findall(_read(_ENGLISH))


@pytest.mark.parametrize("translation", _TRANSLATIONS, ids=lambda path: path.name)
def test_same_tables_and_a_picture_in_its_own_language(translation: Path) -> None:
    text = _read(translation)
    assert _table_rows(text) == _table_rows(_read(_ENGLISH))
    language = translation.stem.removeprefix("README_")
    assert _IMAGE.findall(text) == [f"../docs/images/main_window_{language}.png"]
    assert (_ROOT / "docs" / "images" / f"main_window_{language}.png").is_file()


def test_the_english_readme_shows_the_english_picture() -> None:
    assert _IMAGE.findall(_read(_ENGLISH)) == ["docs/images/main_window_en.png"]
