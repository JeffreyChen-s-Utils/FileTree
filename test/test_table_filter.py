"""The cached any-column table filter keeps Qt's fixed-string semantics (U-20261017-74)."""

import pytest
from PySide6.QtCore import QSortFilterProxyModel, Qt

from je_file_tree.core.node import Node
from je_file_tree.gui.tables import SORT_ROLE, LargestFilesModel, TableProxy

_NAMES = ["Report.PDF", "資料夾-照片.jpg", "Ünïcødé ÉTÉ.txt", "a\tb.bin", "1536.dat", "folder-05.iso", "naïve café.doc"]


def _model():
    root = Node("C:/owned", True, children=[])
    folders = [Node(name, True, children=[], parent=root) for name in ("Photos", "下載", "Backup 2026")]
    root.children.extend(folders)
    files = []
    for number, name in enumerate(_NAMES * 3):
        parent = folders[number % len(folders)]
        node = Node(f"{number}-{name}", False, size=number * 1536, modified=1_780_000_000 + number, parent=parent)
        parent.children.append(node)
        files.append(node)
    model = LargestFilesModel()
    model.set_rows(files)
    return model, files


def _rows(proxy):
    return [proxy.index(row, 0).data() for row in range(proxy.rowCount())]


def _proxies(model):
    cached, reference = TableProxy(), QSortFilterProxyModel()
    for proxy in (cached, reference):
        proxy.setSourceModel(model)
        proxy.setSortRole(SORT_ROLE)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy.setFilterKeyColumn(-1)
    return cached, reference


@pytest.mark.parametrize("needle", ["", "pdf", "REPORT", "資料", "照片", "ünï", "été", "CAFÉ", "1.5 kb", "kb",
                                    "photos", "backup 2026", "下載", "\t", "a\tb", "zzz", "2026-", "-0"])
def test_cached_filter_matches_qt_fixed_string_filter(qapp, needle):
    model, _files = _model()
    cached, reference = _proxies(model)
    cached.setFilterFixedString(needle)
    reference.setFilterFixedString(needle)
    assert _rows(cached) == _rows(reference)


def test_filter_text_follows_units_sorting_and_new_rows(qapp):
    model, files = _model()
    cached, reference = _proxies(model)
    for proxy in (cached, reference):
        proxy.setFilterFixedString("1,536 b")
    assert _rows(cached) == _rows(reference) == []  # sizes still read "1.5 KB"
    model.unit = "B"
    model.refresh()
    for proxy in (cached, reference):
        proxy.invalidate()
    assert _rows(cached) == _rows(reference) and _rows(cached)
    cached.sort(1, Qt.SortOrder.AscendingOrder)
    assert _rows(cached) == sorted(_rows(cached), key=lambda name: next(
        node.size for node in files if node.name == name))
    model.set_rows(files[:2])
    cached.setFilterFixedString("")
    assert _rows(cached) == [files[0].name, files[1].name]  # the new rows, still sorted by size


def test_other_filter_settings_fall_back_to_qt(qapp):
    model, _files = _model()
    cached, reference = _proxies(model)
    for proxy in (cached, reference):
        proxy.setFilterKeyColumn(0)
        proxy.setFilterFixedString("photos")  # folder column only: no name matches
    assert _rows(cached) == _rows(reference) == []
    for proxy in (cached, reference):
        proxy.setFilterRegularExpression("^0-")
    assert _rows(cached) == _rows(reference) == ["0-Report.PDF"]


@pytest.mark.parametrize("kind", ["regex", "wildcard"])
def test_a_later_regex_or_wildcard_replaces_the_cached_fixed_string(qapp, kind):
    model, _files = _model()
    cached, reference = _proxies(model)
    for proxy in (cached, reference):
        proxy.setFilterFixedString("photos")
        if kind == "regex":
            proxy.setFilterRegularExpression("^1-")
        else:
            proxy.setFilterWildcard("*.iso")
    assert _rows(cached) == _rows(reference) and _rows(cached)
