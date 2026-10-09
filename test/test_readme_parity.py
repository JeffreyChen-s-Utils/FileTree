"""Translated documents follow the English one: same sections, same commands, same tables (and pictures)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_ENGLISH = _ROOT / "README.md"
_TRANSLATIONS = sorted((_ROOT / "README").glob("README_*.md"))
_NUITKA = _ROOT / "nuitka.md"
_NUITKA_TRANSLATIONS = [_ROOT / f"nuitka.{language}.md" for language in ("zh-TW", "zh-CN", "ja", "ko")]
_PAIRS = [(_ENGLISH, path) for path in _TRANSLATIONS] + [(_NUITKA, path) for path in _NUITKA_TRANSLATIONS]
_CODE_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _heading_levels(text: str) -> list[int]:
    without_code = _CODE_BLOCK.sub("", text)
    return [len(match.group(1)) for match in re.finditer(r"^(#{1,6}) ", without_code, re.MULTILINE)]


def _table_rows(text: str) -> int:
    return len(re.findall(r"^\|", _CODE_BLOCK.sub("", text), re.MULTILINE))


def _table_cells(text: str) -> list[list[str]]:
    """Read cell boundaries outside inline code, including the final delimiter."""
    rows = []
    for line in _CODE_BLOCK.sub("", text).splitlines():
        if line.startswith("|"):
            assert line.endswith("|"), line
            cells = re.split(r"\|(?=(?:[^`]*`[^`]*`)*[^`]*$)", line)
            rows.append([cell.strip() for cell in cells[1:-1]])
    return rows


def test_every_language_is_there() -> None:
    assert [path.name for path in _TRANSLATIONS] == ["README_ja.md", "README_ko.md",
                                                   "README_zh-CN.md", "README_zh-TW.md"]


def _pair_id(pair: tuple[Path, Path]) -> str:
    return pair[1].name


def test_every_nuitka_guide_is_there() -> None:
    assert all(path.is_file() for path in [_NUITKA, *_NUITKA_TRANSLATIONS])


@pytest.mark.parametrize("pair", _PAIRS, ids=_pair_id)
def test_same_sections(pair: tuple[Path, Path]) -> None:
    english, translation = pair
    assert _heading_levels(_read(translation)) == _heading_levels(_read(english))


@pytest.mark.parametrize("pair", _PAIRS, ids=_pair_id)
def test_same_commands(pair: tuple[Path, Path]) -> None:
    english, translation = pair
    assert _CODE_BLOCK.findall(_read(translation)) == _CODE_BLOCK.findall(_read(english))


@pytest.mark.parametrize("pair", _PAIRS, ids=_pair_id)
def test_same_tables(pair: tuple[Path, Path]) -> None:
    english, translation = pair
    assert _table_rows(_read(translation)) == _table_rows(_read(english))
    assert [len(row) for row in _table_cells(_read(translation))] == [
        len(row) for row in _table_cells(_read(english))
    ]


@pytest.mark.parametrize("translation", _TRANSLATIONS, ids=lambda path: path.name)
def test_shortcut_keys_preserved(translation: Path) -> None:
    keys = {"Ctrl+O", "F5", "Esc", "Ctrl+F", "Delete", "F1", "Ctrl+Q"}
    translated = {row[0] for row in _table_cells(_read(translation))}
    assert keys <= translated


@pytest.mark.parametrize("translation", _TRANSLATIONS, ids=lambda path: path.name)
def test_a_picture_in_its_own_language(translation: Path) -> None:
    text = _read(translation)
    language = translation.stem.removeprefix("README_")
    assert _IMAGE.findall(text) == [f"../docs/images/main_window_{language}.png"]
    assert (_ROOT / "docs" / "images" / f"main_window_{language}.png").is_file()


def test_the_english_readme_shows_the_english_picture() -> None:
    assert _IMAGE.findall(_read(_ENGLISH)) == ["docs/images/main_window_en.png"]
